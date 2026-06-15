#!/usr/bin/env python3
"""AI+酶工程 每日文献清单生成器 (v2 - 改进版)"""
import json, logging, os, sys, time, traceback
from datetime import datetime
from typing import Any, Optional
import requests

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(WORK_DIR, "output")
JOURNALS_DB = os.path.join(WORK_DIR, "journals_db.json")
OA_BASE = "https://api.openalex.org"
API_DELAY = 0.3

# 搜索查询：更聚焦 AI+酶工程
SEARCH_TOPICS = [
    "enzyme engineering machine learning",
    "deep learning protein design",
    "protein language model enzyme function prediction",
    "directed evolution machine learning protein",
    "computational enzyme design AI",
    "deep learning enzyme catalysis",
    "AI enzyme engineering protein engineering",
    "machine learning enzyme activity protein engineering",
    "deep learning protein structure enzyme design",
]

# 核心关键词（用于相关度过滤和多样性筛选）
CORE_KEYWORDS = [
    "enzyme", "protein engineering", "protein design",
    "enzyme engineering", "enzyme design", "catalytic",
    "directed evolution", "protein structure", "protein function",
    "protein sequence", "biocatalysis", "enzyme activity",
    "enzyme catalysis", "binding affinity", "substrate",
    "active site", "enzyme optimization", "protein folding",
    "protein language model", "protein representation",
    "enzyme mechanism", "enzyme kinetics",
]

# 排除词（避免不相干的高引综述混入）
EXCLUDE_KEYWORDS = [
    "large language model", "llm", "chatgpt", "gpt-4",
    "neuroinflammation", "neurodegenerative", "extracellular vesicle",
    "medical image", "image segmentation", "autonomous agent",
    "social media", "clinical trial", "patient",
    "survey of large language", "hallucination",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

_session = requests.Session()
_session.headers.update({"User-Agent": "DailyPaperList/1.0", "Accept": "application/json"})
_last_call = 0.0

def _rl():
    global _last_call
    e = time.time() - _last_call
    if e < API_DELAY: time.sleep(API_DELAY - e)
    _last_call = time.time()

def oa_get(url, params, retries=3):
    for a in range(retries):
        _rl()
        try:
            r = _session.get(url, params=params, timeout=20)
            if r.status_code == 429:
                w=(a+1)*5; log.warning(f"429 等待{w}s"); time.sleep(w); continue
            r.raise_for_status(); return r.json()
        except Exception as e:
            log.warning(f"请求失败({a+1}): {e}"); time.sleep(2*(a+1))
    return None

def load_json(p):
    with open(p,"r",encoding="utf-8") as f: return json.load(f)
def save_json(p,d):
    with open(p,"w",encoding="utf-8") as f: json.dump(d,f,ensure_ascii=False,indent=2)

def load_journals_db(p):
    try: j=load_json(p); log.info(f"期刊数据库: {len(j)}条"); return j
    except FileNotFoundError: return []

def lookup_journal(venue, db):
    if not venue or not db: return None
    vl=venue.strip().lower()
    for j in db:
        for n in [j["name"]]+j.get("aliases",[]):
            if n.lower()==vl or n.lower() in vl or vl in n.lower():
                return {"name":j["name"],"if":j["if"],"cas_rank":j["cas_rank"]}
    return None

def reconstruct_abstract(inv_idx):
    if not inv_idx: return ""
    wp=[]
    for w,ps in inv_idx.items():
        for p in ps: wp.append((p,w))
    wp.sort(key=lambda x:x[0])
    return " ".join(w for _,w in wp)

def is_relevant(title, abstract):
    """判断论文是否与 AI+酶工程相关"""
    txt = (title + " " + abstract).lower()
    # 排除检查
    for ek in EXCLUDE_KEYWORDS:
        if ek in txt and "enzyme" not in txt:
            return False
    # 核心相关度：必须包含至少 2 个核心关键词或 1 个明确相关词
    core_matches = sum(1 for kw in CORE_KEYWORDS if kw in txt)
    if core_matches >= 2: return True
    # 弱相关：至少有 AI 关键词 + 1 个生物关键词
    ai_kws = ["deep learning","machine learning","neural network","transformer",
              "artificial intelligence","computational","prediction"]
    bio_kws = ["protein","enzyme","catalytic","amino acid","sequence","molecular",
               "binding","folding","structure prediction"]
    has_ai = any(kw in txt for kw in ai_kws)
    has_bio = sum(1 for kw in bio_kws if kw in txt) >= 2
    return has_ai and has_bio

def search_works(query, limit=20, years="2024-"):
    data = oa_get(f"{OA_BASE}/works", {
        "search": query, "sort": "cited_by_count:desc",
        "per_page": min(limit,50),
        "filter": f"publication_year:{years}",
        "select": "id,doi,title,authorships,primary_location,publication_date,abstract_inverted_index,concepts,cited_by_count,type_crossref,language",
    })
    results = data.get("results",[]) if data else []
    log.info(f"  >>> '{query[:45]}' -> {len(results)}篇")
    return results

def get_venue(pl):
    if isinstance(pl,dict):
        s=pl.get("source")
        if s: return s.get("display_name","")
    return ""

def get_authors(authorships):
    if not authorships: return []
    ns=[]
    for a in authorships:
        au=a.get("author") if isinstance(a,dict) else None
        if au: ns.append(au.get("display_name",""))
    return [n for n in ns if n]

def get_concepts(w,n=3):
    cs=w.get("concepts") or []
    cs.sort(key=lambda c:c.get("score",0),reverse=True)
    return [c["display_name"] for c in cs[:n]]

def score_work(w,db):
    """评分：相关度权重 > 引用数 > 期刊影响力"""
    txt = ((w.get("title") or "") + " " + reconstruct_abstract(w.get("abstract_inverted_index"))).lower()
    # 相关度评分 (0-60分)
    rel_score=0
    for kw in CORE_KEYWORDS:
        if kw in txt: rel_score+=6
    ai_kws=["deep learning","machine learning","neural network","transformer",
            "language model","diffusion","graph neural","artificial intelligence"]
    for kw in ai_kws:
        if kw in txt: rel_score+=8
    if "enzyme" in txt: rel_score+=10  # 明确涉及酶学加高分
    # 引用数 (0-15分)
    cite_score = min((w.get("cited_by_count") or 0)/30.0, 15.0)
    # 期刊 (0-15分)
    ji = lookup_journal(get_venue(w.get("primary_location")), db)
    journal_score=0
    if ji:
        journal_score += min(ji["if"]/15.0, 8.0)
        journal_score += 7.0 if ji["cas_rank"]=="一区" else 3.0 if ji["cas_rank"]=="二区" else 0
    # 年份加分 (0-10分)
    y=w.get("year") or 0; cy=datetime.now().year
    year_score = 10 if y>=cy else 8 if y==cy-1 else 5 if y>=cy-2 else 2 if y>=cy-3 else 0
    s = rel_score*1.5 + cite_score + journal_score + year_score
    return s

def build_entry(w,db):
    v=get_venue(w.get("primary_location"))
    ji=lookup_journal(v,db)
    pd=w.get("publication_date","") or ""
    py=pd[:4] if len(pd)>=4 else str(w.get("publication_year",""))
    pm=pd[5:7] if len(pd)>=7 else ""
    doi=(w.get("doi") or "").replace("https://doi.org/","")
    return {
        "id":w.get("id",""), "title":w.get("title","N/A"),
        "doi":doi, "url":f"https://doi.org/{doi}" if doi else "",
        "abstract":reconstruct_abstract(w.get("abstract_inverted_index")),
        "authors":get_authors(w.get("authorships")),
        "authors_short":", ".join(get_authors(w.get("authorships"))[:5])+(" et al." if len(get_authors(w.get("authorships")))>5 else ""),
        "venue":v, "journal_info":ji,
        "publication_date":pd, "year":py, "month":pm,
        "citations":w.get("cited_by_count") or 0,
        "concepts":get_concepts(w), "source":"OpenAlex",
    }

def main():
    log.info("="*50); log.info("AI+酶工程 每日文献清单 v2"); log.info("="*50)
    db=load_journals_db(JOURNALS_DB)

    # 1. 搜索 & 去重 & 相关度过滤
    all_works={}; seen_doi=set()
    for q in SEARCH_TOPICS:
        for w in search_works(q):
            wid=w.get("id",""); doi=w.get("doi","") or ""
            title=(w.get("title") or "").strip().lower()
            abstract=reconstruct_abstract(w.get("abstract_inverted_index"))
            if not wid or not title or not abstract: continue
            if doi in seen_doi: continue
            if not is_relevant(title, abstract): continue
            seen_doi.add(doi); all_works[wid]=w

    log.info(f"相关度过滤后: {len(all_works)} 篇")
    if not all_works: log.warning("未获取到论文"); return

    # 2. 评分排序 + 多样性筛选
    scored=sorted([(score_work(w,db),wid,w) for wid,w in all_works.items()], key=lambda x:x[0], reverse=True)
    selected=[scored[0]]; ckws=set()
    kwl=["deep learning","language model","diffusion","graph","directed evolution",
         "protein design","enzyme catalysis","molecular dynamics"]
    for s,wid,w in scored[1:]:
        if len(selected)>=10: break
        txt=((w.get("title") or "")+ " "+reconstruct_abstract(w.get("abstract_inverted_index") or {})).lower()
        pk={k for k in kwl if k in txt}
        if pk-ckws or len(selected)<10:
            selected.append((s,wid,w)); ckws.update(pk)
    log.info(f"最终选取 {len(selected)} 篇")

    # 3. 输出 JSON
    entries=[build_entry(w,db) for _,_,w in selected]
    os.makedirs(OUTPUT_DIR,exist_ok=True)
    today=datetime.now().strftime("%Y-%m-%d")
    jp=os.path.join(OUTPUT_DIR,f"papers_raw_{today}.json")
    save_json(jp,{"generated_at":datetime.now().isoformat(),"total_works":len(all_works),"papers":entries})
    print("")
    print("="*50)
    print(f"数据保存: {jp}")
    print(f"共 {len(entries)} 篇论文精选")
    print("精选论文:")
    for i,e in enumerate(entries,1):
        ji=e.get("journal_info")
        jn=ji["name"] if ji else (e.get("venue","")[:25] or "N/A")
        print(f"  {i}. [{e['year']}] {e['title'][:70]}... ({jn})")
    print("="*50)

if __name__=="__main__":
    try: main()
    except KeyboardInterrupt: sys.exit(1)
    except Exception as e: log.error(f"失败: {e}"); traceback.print_exc(); sys.exit(1)
