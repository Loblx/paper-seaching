#!/usr/bin/env python3
"""排版脚本：读取 papers_raw_*.json → 生成 Markdown（翻译由自动化模型补充）"""
import json, os, sys, logging
from datetime import datetime

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(WORK_DIR, "output")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

def load_latest_json():
    fs = [f for f in os.listdir(OUTPUT_DIR) if f.startswith("papers_raw_") and f.endswith(".json")]
    if not fs: log.error("未找到数据文件"); sys.exit(1)
    p = os.path.join(OUTPUT_DIR, max(fs))
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def gen_rec(p):
    txt = ((p.get("title") or "") + " " + (p.get("abstract") or "")).lower()
    cs = p.get("concepts", [])
    ji = p.get("journal_info")
    tags = []
    for kw, lb in [("deep learning","深度学习"),("neural network","深度学习"),
        ("transformer","Transformer"),("language model","蛋白质语言模型"),
        ("diffusion","生成式AI"),("graph neural","图神经网络"),
        ("reinforcement","强化学习"),("directed evolution","定向进化"),
        ("enzyme design","酶设计"),("catalytic","酶催化"),
        ("protein design","蛋白质设计"),("protein structure","蛋白质结构"),
        ("high-throughput","高通量筛选"),("active learning","主动学习"),
        ("molecular dynamics","分子动力学"),("alphafold","AlphaFold"),
        ("protein engineering","蛋白质工程"),("enzyme engineering","酶工程")]:
        if kw in txt: tags.append(lb)
    if not tags and cs: tags = cs[:2]
    parts = [f"方向{'、'.join(tags[:3])}"]
    ms = []
    if "pretrained" in txt or "pre-trained" in txt: ms.append("预训练模型")
    if "zero-shot" in txt or "few-shot" in txt: ms.append("零样本/少样本学习")
    if ms: parts.append(f"采用{'、'.join(ms)}等技术")
    ct = p.get("citations") or 0
    parts.append(f"引用{ct}次" if ct>=10 else "新近发表")
    parts.append(f"发表于{p.get('year','')}年")
    if ji: parts.append(f"期刊{ji['name']}（中科院{ji['cas_rank']}，IF={ji['if']}）")
    return "；".join(parts) + "。"

def gen_md(data):
    ps = data["papers"]
    ls = [
        "# {emoji_book} 天然产物与P450工程 每日必读文献清单",
        "",
        f"**生成日期**: {datetime.now().strftime('%Y年%m月%d日')}",
        "",
        "*本清单通过 OpenAlex API 自动检索，聚焦截短侧耳素/紫杉醇、P450/CPR、酵母底盘、选择性与AI酶工程的近期论文。*",
        f"**数据统计**: 共检索 {data.get('total_works',0)} 篇论文，精选 {len(ps)} 篇。",
        "",
        "---", "",
    ]
    ls[0] = ls[0].replace("{emoji_book}", "\U0001F4DA")

    # 总表
    ls.append("| # | 标题 | 期刊 | 年份 | 引用 |"); ls.append("|---|------|------|------|------|")
    for i,p in enumerate(ps,1):
        ts = (p.get("title","")[:70]+"...") if len(p.get("title",""))>70 else p.get("title","")
        ji=p.get("journal_info"); jn=ji["name"] if ji else (p.get("venue","")[:20] or "N/A")
        ls.append(f"| {i} | {ts} | {jn} | {p.get('year','')} | {p.get('citations',0)} |")
    ls.append(""); ls.append("---"); ls.append("")

    # 详细条目
    for i,p in enumerate(ps,1):
        t=p.get("title","N/A"); u=p.get("url",""); ab=p.get("abstract","") or ""
        au=p.get("authors_short","N/A"); ve=p.get("venue",""); ji=p.get("journal_info")
        pd=f"{p.get('year','')}-{p.get('month','')}" if p.get('month') else p.get('year','')
        ct=p.get("citations",0); cs=", ".join(p.get("concepts",[]))
        rc=gen_rec(p)
        log.info(f"  [{i}] {t[:60]}...")
        ls.append(f"## {i}. [{t}]({u})" if u else f"## {i}. {t}"); ls.append("")
        meta=[]
        if ve: meta.append(f"**期刊**: {ji['name']}（中科院{ji['cas_rank']}，IF={ji['if']}）" if ji else ve)
        meta.append(f"**发表日期**: {pd}"); meta.append(f"**引用**: {ct}次")
        if cs: meta.append(f"**主题**: {cs}")
        ls.append(" | ".join(meta)); ls.append("")
        ls.append(f"**作者**: {au}"); ls.append("")
        if ab:
            ls.append("**摘要 (English)**:\n"); ls.append(f"> {ab}\n")
            ls.append("**摘要 (中文翻译)**:\n"); ls.append("> *(待模型翻译补充)*\n")
        ls.append(f"**推荐理由**: {rc}"); ls.append("")
        if p.get("doi"): ls.append(f"> DOI: [{p['doi']}](https://doi.org/{p['doi']})"); ls.append("")
        if i<len(ps): ls.append("---\n")
    ls.append("---"); ls.append("")
    ls.append(f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 数据来源: [OpenAlex](https://openalex.org/)*")
    return "\n".join(ls)

def main():
    log.info("="*30); log.info("文献排版脚本"); log.info("="*30)
    d=load_latest_json()
    log.info(f"加载 {len(d['papers'])} 篇论文")
    md=gen_md(d)
    t=datetime.now().strftime("%Y-%m-%d")
    o=os.path.join(OUTPUT_DIR,f"daily_reading_{t}.md")
    with open(o,"w",encoding="utf-8") as f: f.write(md)
    log.info(f"已保存: {o}")
    print(f"[OK] {o}")

if __name__=="__main__":
    try: main()
    except KeyboardInterrupt: sys.exit(1)
    except Exception as e: log.error(f"失败: {e}"); import traceback; traceback.print_exc(); sys.exit(1)
