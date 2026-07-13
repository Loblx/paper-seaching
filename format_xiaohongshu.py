#!/usr/bin/env python3
"""format_xiaohongshu.py — 生成小红书格式的论文摘要文案"""

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

def gen_posts(data):
    papers = data.get("papers", [])
    today = datetime.now(); date_tag = today.strftime("%Y-%m-%d")
    total = data.get("total_works", 0)

    posts = []
    posts.append(f"【天然产物与P450工程 每日文献速递 {date_tag}】")
    posts.append(f"📊 今日从 OpenAlex 检索 {total} 篇论文，精选 {len(papers)} 篇推荐")
    posts.append("")
    posts.append("─" * 25)
    posts.append("")

    for i, p in enumerate(papers, 1):
        title = p.get("title", "N/A")
        authors = p.get("authors_short", "N/A")
        ji = p.get("journal_info")
        jn = f"{ji['name']}（IF={ji['if']}）" if ji else (p.get("venue","") or "")
        ct = p.get("citations", 0)
        yr = p.get("year", "")
        doi = p.get("doi", "")
        ab_cn = p.get("abstract_cn", "") or ""
        ab_en = p.get("abstract", "") or ""

        # 提取关键信息
        summary = ""
        if ab_cn and ab_cn not in ("[翻译失败]", ""):
            summary = ab_cn[:150]
            if len(ab_cn) > 150:
                summary = summary.rsplit("。", 1)[0] + "。"
        elif ab_en:
            summary = ab_en[:200] + "..."

        tags = ["#AI", "#酶工程", "#蛋白质工程"]
        if "deep learning" in (p.get("abstract","") + p.get("title","")).lower():
            tags.append("#深度学习")
        if "language model" in (p.get("abstract","") + p.get("title","")).lower():
            tags.append("#蛋白质语言模型")
        if "directed evolution" in (p.get("abstract","") + p.get("title","")).lower():
            tags.append("#定向进化")

        posts.append(f"📌 {i}. {title}")
        posts.append(f"   📰 {jn} | {yr}年 | 引用{ct}次")
        posts.append(f"   👥 {authors}")
        if summary:
            posts.append(f"   💡 {summary}")
        if doi:
            posts.append(f"   🔗 https://doi.org/{doi}")
        posts.append(f"   {' '.join(tags)}")
        posts.append("")
        posts.append(f"📖 展开查看全文" if i < len(papers) else "")
        if i < len(papers):
            posts.append("")
            posts.append("─" * 25)
            posts.append("")

    posts.append("")
    posts.append("💬 关注我，每天推送天然产物、P450/CPR与AI酶工程的近期论文！")
    posts.append("🎯 数据来源：OpenAlex | 翻译：DeepSeek")
    return "\n".join(posts)

def main():
    log.info("="*40); log.info("小红书文案生成"); log.info("="*40)
    data, source_path = load_latest_data()
    log.info(f"加载 {len(data['papers'])} 篇论文")
    text = gen_posts(data)
    today = datetime.now().strftime("%Y-%m-%d")
    p = os.path.join(OUTPUT_DIR, f"xiaohongshu_{today}.md")
    with open(p, "w", encoding="utf-8") as f: f.write(text)
    log.info(f"已保存: {p}"); print(f"[OK] 小红书文案 -> {p}")

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: sys.exit(1)
    except Exception as e: log.error(f"失败: {e}"); import traceback; traceback.print_exc(); sys.exit(1)
