#!/usr/bin/env python3
"""format_wechat.py — 生成微信公众号文章格式的日报"""

import json, logging, os, sys
from datetime import datetime

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(WORK_DIR, "output")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

def load_latest_data():
    for prefix in ["papers_translated_", "papers_raw_"]:
        fs = [f for f in os.listdir(OUTPUT_DIR) if f.startswith(prefix) and f.endswith(".json")]
        if fs:
            p = os.path.join(OUTPUT_DIR, max(fs))
            with open(p, "r", encoding="utf-8") as f: return json.load(f), p
    log.error("未找到数据文件"); sys.exit(1)

def shorten(abstract, max_len=300):
    if not abstract: return ""
    if len(abstract) <= max_len: return abstract
    return abstract[:max_len].rsplit(" ", 1)[0] + "……"

def gen_article(data):
    papers = data.get("papers", [])
    today = datetime.now(); date_str = today.strftime("%Y年%m月%d日"); date_tag = today.strftime("%Y-%m-%d")
    total = data.get("total_works", 0)

    lines = []
    lines.append(f"# 📄 AI+酶工程 每日文献速递")
    lines.append(f"")
    lines.append(f"> 生成日期：{date_str}")
    lines.append(f"> 数据来源：OpenAlex | 共检索 {total} 篇，精选 {len(papers)} 篇")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")

    for i, p in enumerate(papers, 1):
        title = p.get("title", "N/A")
        url = p.get("url", "")
        doi = p.get("doi", "")
        authors = p.get("authors_short", "N/A")
        abstract_cn = p.get("abstract_cn", "") or ""
        abstract_en = p.get("abstract", "") or ""
        ji = p.get("journal_info")
        journal_str = ""
        if ji:
            journal_str = f"{ji['name']}（中科院{ji['cas_rank']}，IF={ji['if']}）"
        else:
            journal_str = p.get("venue", "")

        # 如果中文摘要太长，简短
        if len(abstract_cn) > 200:
            summary = shorten(abstract_cn, 200)
        elif abstract_en:
            summary = shorten(abstract_en, 300)
        else:
            summary = "（摘要未提供）"

        lines.append(f"## {i}. {title}")
        lines.append(f"")
        if url:
            lines.append(f"🔗 [{title}]({url})")
            lines.append(f"")
        lines.append(f"**📰 期刊**：{journal_str}")
        lines.append(f"")
        lines.append(f"**👥 作者**：{authors}")
        lines.append(f"")
        lines.append(f"**📅 年份**：{p.get('year','')}　**📊 引用**：{p.get('citations',0)} 次")
        lines.append(f"")
        if abstract_cn and abstract_cn not in ("[翻译失败]", ""):
            lines.append(f"**📝 摘要（中文）**：")
            lines.append(f"> {abstract_cn}")
            lines.append(f"")
        if doi:
            lines.append(f"DOI: [{doi}](https://doi.org/{doi})")
        lines.append(f"")
        lines.append(f"---")
        lines.append(f"")

    lines.append(f"*由 AI+酶工程 每日文献推送系统自动生成 · {today.strftime('%Y-%m-%d %H:%M')}*")
    return "\n".join(lines)

def main():
    log.info("="*40); log.info("微信文章生成"); log.info("="*40)
    data, source_path = load_latest_data()
    log.info(f"加载 {len(data['papers'])} 篇论文")
    md = gen_article(data)
    today = datetime.now().strftime("%Y-%m-%d")
    p = os.path.join(OUTPUT_DIR, f"wechat_article_{today}.md")
    with open(p, "w", encoding="utf-8") as f: f.write(md)
    log.info(f"已保存: {p}"); print(f"[OK] 微信文章 -> {p}")

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: sys.exit(1)
    except Exception as e: log.error(f"失败: {e}"); import traceback; traceback.print_exc(); sys.exit(1)
