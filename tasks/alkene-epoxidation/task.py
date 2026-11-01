#!/usr/bin/env python3
"""Daily literature digest for alkene epoxidation and oxygen-atom transfer."""
import argparse
import html
import json
import logging
import os
import re
import smtplib
import sys
import time
from datetime import datetime, timedelta
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
try:
    from openai import OpenAI
except ImportError:  # Local dry-runs can work without the optional AI client.
    OpenAI = None

TASK_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = TASK_DIR / "output"
HISTORY_FILE = TASK_DIR / "data" / "paper-history.json"
OPENALEX_WORKS = "https://api.openalex.org/works"
TIMEZONE = ZoneInfo("Asia/Shanghai")
RECENT_DAYS = 120
BACKFILL_DAYS = 730
HISTORY_DAYS = 730
MAX_PAPERS = 6
RECIPIENT = "256677584@qq.com"

SEARCH_QUERIES = [
    "alkene epoxidation electrocatalysis",
    "electrochemical alkene oxidation",
    "electrochemical olefin epoxidation",
    "electrocatalytic epoxidation",
    "direct propylene epoxidation",
    "epoxide electrosynthesis",
    "oxygen atom transfer electrocatalysis",
    "alkene oxidation radical intermediate",
    "olefin oxidation cation effect",
    "epoxidation interfacial electric field",
    "epoxidation metal support interaction",
]

TRANSFORMATION_TOPICS = {
    "烯烃环氧化": (
        "alkene epoxidation", "olefin epoxidation", "electrochemical epoxidation",
        "electro-epoxidation", "ethylene epoxidation", "propylene epoxidation",
        "cyclooctene epoxidation", "epoxide electrosynthesis",
    ),
    "氧原子转移": ("oxygen atom transfer", "oxygen-atom transfer", "oxo transfer"),
}
MECHANISTIC_TOPICS = {
    "电催化": ("electrocatal", "electrochemical catalysis", "electrosynthesis", "electro-epoxidation"),
    "阳离子效应": ("cation effect", "cation-dependent", "alkali cation", "cation-mediated"),
    "金属-载体/界面相互作用": (
        "metal-support interaction", "metal support interaction", "strong metal support interaction",
        "catalyst-support interaction", "core-shell", "supported electrocatalyst", "interface-enhanced",
        "interfacial modulation", "metal-support interface",
    ),
    "自由基中间体": ("radical intermediate", "radical-mediated", "radical pathway", "radical mechanism"),
    "界面电场": ("interfacial electric field", "electric-field", "electric field", "interfacial field"),
}
TITLE_ANCHORS = (
    "epoxid", "alkene", "olefin", "propylene", "ethylene",
    "oxygen atom transfer", "oxygen-atom transfer",
)
TITLE_EXCLUSIONS = (
    "epoxide deoxygenation", "deoxygenation of", "epoxidized natural rubber",
    "difunctionalization", "hydration of alkenes", "electrochemical sensing",
    "cycloaddition", "vinyl epoxide", "ring opening of epoxide", "epoxide ring-opening",
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "paper-seaching-alkene-epoxidation/2.0", "Accept": "application/json"})


def read_json(path, fallback):
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)


def abstract(work):
    index = work.get("abstract_inverted_index") or {}
    tokens = [(position, word) for word, positions in index.items() for position in positions]
    return " ".join(word for _, word in sorted(tokens))


def normalized_id(work):
    doi = (work.get("doi") or "").lower().replace("https://doi.org/", "")
    return f"doi:{doi}" if doi else f"openalex:{work.get('id', '')}"


def topic_hits(text, topics):
    return [label for label, terms in topics.items() if any(term in text for term in terms)]


def transformation_hits(title, text):
    hits = topic_hits(text, TRANSFORMATION_TOPICS)
    if "烯烃环氧化" not in hits:
        epoxidation = "epoxid" in text or "epoxide electrosynthesis" in text
        alkene = any(term in text for term in ("alkene", "olefin", "propylene", "ethylene", "cyclooctene"))
        if epoxidation and alkene:
            hits.append("烯烃环氧化")
    return hits


def classify(work):
    title = (work.get("title") or "").lower()
    text = f"{title} {abstract(work)}".lower()
    transformations = transformation_hits(title, text)
    mechanisms = topic_hits(text, MECHANISTIC_TOPICS)
    has_anchor = any(anchor in title for anchor in TITLE_ANCHORS)
    excluded = any(term in title for term in TITLE_EXCLUSIONS)
    return transformations, mechanisms, has_anchor and not excluded


def matches_query(work):
    transformations, mechanisms, title_ok = classify(work)
    return bool(title_ok and transformations and mechanisms)


def load_history(today):
    cutoff = today - timedelta(days=HISTORY_DAYS)
    history = read_json(HISTORY_FILE, {"papers": []})
    papers = []
    for item in history.get("papers", []):
        try:
            if datetime.fromisoformat(item["sent_on"]).date() >= cutoff:
                papers.append(item)
        except (KeyError, ValueError):
            pass
    return papers


def openalex(query, start, end, retries=3):
    filters = ",".join((
        f"from_publication_date:{start.isoformat()}",
        f"to_publication_date:{end.isoformat()}",
        "type:article|preprint",
    ))
    params = {
        "search": query,
        "filter": filters,
        "sort": "relevance_score:desc",
        "per-page": 100,
        "select": "id,doi,title,publication_date,authorships,primary_location,abstract_inverted_index,cited_by_count",
    }
    mailto = os.getenv("OPENALEX_MAILTO") or os.getenv("QQ_EMAIL")
    if mailto:
        params["mailto"] = mailto
    for attempt in range(retries):
        try:
            response = SESSION.get(OPENALEX_WORKS, params=params, timeout=30)
            response.raise_for_status()
            return response.json().get("results", [])
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    return []


def fetch_candidates(today, sent_ids):
    candidates = {}

    def collect(start, tier):
        for query in SEARCH_QUERIES:
            try:
                works = openalex(query, start, today)
            except requests.RequestException as error:
                log.warning("OpenAlex failed for %s: %s", query, error)
                continue
            matched = 0
            for work in works:
                key = normalized_id(work)
                if key in sent_ids or not work.get("title") or not abstract(work) or not matches_query(work):
                    continue
                record = candidates.setdefault(key, work)
                record.setdefault("_matched_queries", [])
                if query not in record["_matched_queries"]:
                    record["_matched_queries"].append(query)
                record["_retrieval_tier"] = min(record.get("_retrieval_tier", tier), tier)
                matched += 1
            log.info("%s -> raw=%s matched=%s", query, len(works), matched)

    collect(today - timedelta(days=RECENT_DAYS), 0)
    if len(candidates) < MAX_PAPERS:
        log.info("Only %s unseen recent candidates; backfilling %s days.", len(candidates), BACKFILL_DAYS)
        collect(today - timedelta(days=BACKFILL_DAYS), 1)
    return candidates


def score(work, today):
    transformations, mechanisms, _ = classify(work)
    title = (work.get("title") or "").lower()
    try:
        age = (today - datetime.fromisoformat(work.get("publication_date") or "").date()).days
    except ValueError:
        age = BACKFILL_DAYS
    recency = max(0, 60 - 60 * age / BACKFILL_DAYS)
    title_focus = 35 if ("epoxid" in title or "oxygen atom transfer" in title or "oxygen-atom transfer" in title) else 15
    query_support = min(len(work.get("_matched_queries", [])) * 4, 20)
    backfill_penalty = 8 * work.get("_retrieval_tier", 0)
    citation_tiebreaker = min((work.get("cited_by_count") or 0) / 100, 2)
    return 30 * len(transformations) + 18 * len(mechanisms) + title_focus + query_support + recency + citation_tiebreaker - backfill_penalty


def select(candidates, today):
    selected, topic_count = [], {}
    for work in sorted(candidates.values(), key=lambda item: score(item, today), reverse=True):
        _, mechanisms, _ = classify(work)
        if len(selected) >= MAX_PAPERS:
            break
        if mechanisms and all(topic_count.get(tag, 0) >= 3 for tag in mechanisms):
            continue
        work["relevance_score"] = round(score(work, today), 2)
        work["research_topics"] = transformation_hits("", f"{work.get('title', '')} {abstract(work)}".lower()) + mechanisms
        selected.append(work)
        for tag in mechanisms:
            topic_count[tag] = topic_count.get(tag, 0) + 1
    return selected


def extract_json(text):
    if not text:
        return None
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.S)
    match = re.search(r"\{.*\}", cleaned, flags=re.S)
    try:
        return json.loads(match.group(0) if match else cleaned)
    except json.JSONDecodeError:
        return None


def enrich_with_deepseek(papers):
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if OpenAI is None or not api_key or not papers:
        log.info("DeepSeek SDK/key unavailable or no papers; using English fallback fields.")
        return
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    system_prompt = """你是电催化与氧化反应领域的中文文献简报编辑。根据英文题名、摘要和主题，严格输出 JSON：
{"title_cn":"准确中文标题","summary_cn":"2-3句中文摘要要点","relevance_cn":"1-2句说明与烯烃环氧化、氧原子转移或指定机理主题的关系"}
不得臆造实验数据；保留催化剂、化学式、缩写和关键数值；只输出 JSON。"""
    for index, paper in enumerate(papers, 1):
        payload = {
            "title_en": paper.get("title", ""),
            "abstract_en": abstract(paper),
            "topics": paper.get("research_topics", []),
        }
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                temperature=0.2,
                max_tokens=1200,
            )
            result = extract_json(response.choices[0].message.content)
            if not isinstance(result, dict):
                raise ValueError("DeepSeek did not return valid JSON")
            paper["title_cn"] = str(result.get("title_cn", "")).strip()
            paper["summary_cn"] = str(result.get("summary_cn", "")).strip()
            paper["relevance_cn"] = str(result.get("relevance_cn", "")).strip()
            log.info("DeepSeek brief %s/%s completed", index, len(papers))
        except Exception as error:
            log.warning("DeepSeek brief failed for %s: %s", paper.get("title", ""), error)
        if index < len(papers):
            time.sleep(0.8)


def authors(work):
    names = [item.get("author", {}).get("display_name", "") for item in work.get("authorships") or []]
    names = [name for name in names if name]
    return ", ".join(names[:5]) + (" et al." if len(names) > 5 else "")


def link(work):
    doi = (work.get("doi") or "").replace("https://doi.org/", "")
    return f"https://doi.org/{doi}" if doi else work.get("id", "")


def digest_html(papers, generated_at):
    cards = []
    for number, paper in enumerate(papers, 1):
        title_en = paper.get("title", "")
        title_cn = paper.get("title_cn") or "中文标题暂缺"
        summary = paper.get("summary_cn") or abstract(paper)[:700] + ("…" if len(abstract(paper)) > 700 else "")
        relevance = paper.get("relevance_cn") or "根据检索词与题名/摘要匹配入选，建议结合原文核验具体机理证据。"
        tags = paper.get("research_topics", [])
        cards.append(f"""<article>
<div class=number>{number:02d}</div><div class=content>
<h2>{html.escape(title_cn)}</h2><p class=en>{html.escape(title_en)}</p>
<p class=meta>{html.escape(paper.get('publication_date') or '日期待定')} · {html.escape(authors(paper))}</p>
<p class=label>内容要点</p><p>{html.escape(summary)}</p>
<p class=label>研究相关性</p><p>{html.escape(relevance)}</p>
<p class=tags>{' · '.join(html.escape(tag) for tag in tags)}</p>
<a href=\"{html.escape(link(paper))}\">查看原文 ↗</a>
</div></article>""")
    return f"""<!doctype html><html lang=zh-CN><meta charset=utf-8><meta name=viewport content=\"width=device-width,initial-scale=1\">
<title>烯烃环氧化与氧原子转移文献简报</title><style>
body{{font-family:Arial,'Microsoft YaHei',sans-serif;margin:auto;max-width:840px;background:#f2f6f8;color:#17222d;padding:18px;line-height:1.65}}
header,article{{background:white;border-radius:14px;padding:20px;margin-bottom:14px;box-shadow:0 2px 7px #cdd7dd}}
header{{border-top:5px solid #006b78}}h1{{margin:0;color:#005967;font-size:25px}}h2{{font-size:19px;margin:0;color:#173d45}}
article{{display:flex;gap:14px}}.number{{font-size:23px;font-weight:bold;color:#78aeb5}}.content{{min-width:0;flex:1}}
.en,.meta{{color:#667781;font-size:13px}}.label{{font-weight:bold;color:#006b78;margin-bottom:0}}.label+p{{margin-top:2px}}
.tags{{color:#006b78;font-weight:bold;font-size:13px}}a{{color:#006b78}}@media(max-width:600px){{body{{padding:10px}}article{{padding:15px}}}}
</style><header><h1>烯烃环氧化与氧原子转移文献简报</h1>
<p>精确主题优先 · 同义表达扩展 · 近期文献优先 · 跨日去重</p>
<p>生成时间：{generated_at.strftime('%Y-%m-%d %H:%M')}（北京时间）｜本期 {len(papers)} 篇</p></header>
{''.join(cards) or '<article><div class=content>本次没有未推送过的新匹配文献。</div></article>'}</html>"""


def send_email(report, papers, date_tag, dry_run):
    if dry_run:
        log.info("Dry run: email not sent to %s", RECIPIENT)
        return False
    if not papers:
        log.info("No unseen matching papers; email skipped.")
        return False
    sender, auth_code = os.getenv("QQ_EMAIL", ""), os.getenv("QQ_EMAIL_AUTH_CODE", "")
    if not sender or not auth_code:
        raise RuntimeError("QQ_EMAIL or QQ_EMAIL_AUTH_CODE is missing")
    message = MIMEMultipart("alternative")
    message["From"] = formataddr((str(Header("烯烃环氧化文献简报", "utf-8")), sender))
    message["To"] = RECIPIENT
    message["Subject"] = Header(f"[每日文献] 烯烃环氧化与氧原子转移｜{len(papers)}篇｜{date_tag}", "utf-8")
    plain = f"本期筛选 {len(papers)} 篇文献。请使用支持 HTML 的邮件客户端查看完整简报。"
    message.attach(MIMEText(plain, "plain", "utf-8"))
    message.attach(MIMEText(report, "html", "utf-8"))
    with smtplib.SMTP("smtp.qq.com", 587, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(sender, auth_code)
        smtp.sendmail(sender, [RECIPIENT], message.as_string())
    log.info("Digest sent to %s", RECIPIENT)
    return True


def serializable_paper(paper):
    source = ((paper.get("primary_location") or {}).get("source") or {}).get("display_name", "")
    return {
        "id": paper.get("id", ""),
        "doi": paper.get("doi", ""),
        "title": paper.get("title", ""),
        "title_cn": paper.get("title_cn", ""),
        "publication_date": paper.get("publication_date", ""),
        "authors": authors(paper),
        "source": source,
        "citations": paper.get("cited_by_count", 0),
        "research_topics": paper.get("research_topics", []),
        "relevance_score": paper.get("relevance_score", 0),
        "summary_cn": paper.get("summary_cn", ""),
        "relevance_cn": paper.get("relevance_cn", ""),
        "url": link(paper),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Generate a report but do not send email.")
    args = parser.parse_args()
    now = datetime.now(TIMEZONE)
    today = now.date()
    history = load_history(today)
    candidates = fetch_candidates(today, {item["key"] for item in history if item.get("key")})
    papers = select(candidates, today)
    enrich_with_deepseek(papers)
    report = digest_html(papers, now)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT_DIR / f"alkene-epoxidation-digest-{today.isoformat()}.html"
    selection_path = OUTPUT_DIR / f"alkene-epoxidation-selection-{today.isoformat()}.json"
    report_path.write_text(report, encoding="utf-8")
    write_json(selection_path, {
        "generated_at": now.isoformat(),
        "candidate_count": len(candidates),
        "selected_count": len(papers),
        "papers": [serializable_paper(paper) for paper in papers],
    })
    sent = send_email(report, papers, today.isoformat(), args.dry_run)
    if sent:
        history.extend({"key": normalized_id(paper), "sent_on": now.isoformat(), "title": paper["title"]} for paper in papers)
        write_json(HISTORY_FILE, {"updated_at": now.isoformat(), "papers": history})
    for index, paper in enumerate(papers, 1):
        log.info("Selected %s: %s [%s]", index, paper.get("title"), ", ".join(paper.get("research_topics", [])))
    print(f"[OK] candidates={len(candidates)} selected={len(papers)} sent={sent} report={report_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        log.error("Task failed: %s", error)
        sys.exit(1)
