#!/usr/bin/env python3
"""format_html.py — 生成正式、可快速阅读的 HTML 文献简报"""

import json
import logging
import os
import sys
from datetime import datetime

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(WORK_DIR, "output")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)


def load_latest_data():
    for prefix in ["papers_translated_", "papers_raw_"]:
        files = [f for f in os.listdir(OUTPUT_DIR) if f.startswith(prefix) and f.endswith(".json")]
        if files:
            path = os.path.join(OUTPUT_DIR, max(files))
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle), path
    log.error("未找到数据文件")
    sys.exit(1)


def esc(text):
    if text is None:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")


def clean_date(value):
    if not value:
        return "日期信息不完整"
    return value[:10] if len(value) >= 10 else "日期信息不完整"


def journal_label(paper):
    info = paper.get("journal_info")
    if info:
        return f"{info.get('name', '')}（{info.get('cas_rank', '未分区')}，IF={info.get('if', 'N/A')}）"
    return paper.get("venue") or "期刊信息待补充"


def topic_tags(paper):
    topics = paper.get("research_topics") or paper.get("concepts") or []
    return topics[:4]


def short_text(text, fallback):
    text = (text or "").strip()
    if text:
        return text
    return fallback


def gen_html(data):
    papers = data.get("papers", [])
    today = datetime.now()
    date_str = today.strftime("%Y年%m月%d日")
    date_tag = today.strftime("%Y-%m-%d")
    total = data.get("total_works", 0)
    translated = data.get("translation_stats", {}).get("translated", 0)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0">
<title>天然产物与 P450 工程每日文献简报 {date_tag}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:#f3f5f7;color:#172033;font-size:15px;line-height:1.65;-webkit-text-size-adjust:100%}}
.header{{background:#17324d;color:#fff;padding:26px 18px 22px}}
.header h1{{font-size:22px;line-height:1.3;font-weight:700;margin-bottom:8px}}
.header .sub{{font-size:13px;color:#d7e2ee;margin-bottom:16px}}
.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}}
.stat{{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.16);border-radius:8px;padding:8px 10px}}
.stat b{{display:block;font-size:17px;line-height:1.2}}
.stat span{{font-size:11px;color:#d7e2ee}}
.wrap{{padding:14px 12px 22px}}
.section{{background:#fff;border:1px solid #e3e8ef;border-radius:8px;margin-bottom:12px;padding:14px}}
.section h2{{font-size:16px;color:#17324d;margin-bottom:8px}}
.brief{{font-size:13px;color:#4a5568}}
.toc{{list-style:none}}
.toc li{{padding:8px 0;border-top:1px solid #eef2f6}}
.toc li:first-child{{border-top:0}}
.toc a{{color:#17324d;text-decoration:none;font-weight:600}}
.toc .date{{display:inline-block;color:#667085;font-size:12px;min-width:84px}}
.card{{background:#fff;border:1px solid #dfe6ee;border-radius:8px;margin-bottom:12px;overflow:hidden}}
.card-head{{padding:14px 14px 10px;border-bottom:1px solid #edf1f5}}
.index{{display:inline-block;background:#17324d;color:#fff;border-radius:4px;padding:2px 7px;font-size:12px;font-weight:700;margin-bottom:8px}}
.date-line{{font-size:13px;color:#667085;margin-bottom:8px}}
.title-cn{{font-size:17px;line-height:1.45;font-weight:700;color:#172033;margin-bottom:6px}}
.title-en{{font-size:13px;line-height:1.45;color:#526071;font-style:italic}}
.meta{{padding:10px 14px;background:#f8fafc;border-bottom:1px solid #edf1f5;font-size:13px;color:#4a5568}}
.tags{{margin-top:7px}}
.tag{{display:inline-block;background:#e8eef5;color:#344054;border-radius:999px;padding:2px 8px;font-size:12px;margin:2px 4px 2px 0}}
.body{{padding:14px}}
.label{{font-size:13px;font-weight:700;color:#17324d;margin-bottom:4px}}
.text{{font-size:14px;color:#263244;margin-bottom:12px}}
.relevance{{background:#f6f9fc;border-left:3px solid #2764a5;padding:10px 12px;margin-bottom:12px}}
.actions{{margin-top:10px}}
.button{{display:inline-block;background:#17324d;color:#fff;text-decoration:none;border-radius:6px;padding:7px 12px;font-size:13px;font-weight:600}}
details{{margin-top:10px;border-top:1px solid #edf1f5;padding-top:10px}}
summary{{cursor:pointer;color:#2764a5;font-size:13px;font-weight:600}}
.abstract{{font-size:13px;color:#3b4656;margin-top:8px;white-space:pre-wrap}}
.footer{{text-align:center;color:#8390a2;font-size:12px;padding:12px 4px 4px}}
@media(max-width:520px){{.stats{{grid-template-columns:1fr 1fr}}.title-cn{{font-size:16px}}.section,.card{{border-radius:7px}}}}
</style>
</head>
<body>
<div class="header">
  <h1>天然产物与 P450 工程每日文献简报</h1>
  <div class="sub">P450/CPR · 酵母底盘 · 萜类天然产物 · AI 辅助酶工程</div>
  <div class="stats">
    <div class="stat"><b>{date_str}</b><span>推送日期</span></div>
    <div class="stat"><b>{total}</b><span>候选文献</span></div>
    <div class="stat"><b>{len(papers)}</b><span>本期精选</span></div>
  </div>
</div>
<div class="wrap">
  <div class="section">
    <h2>本期概览</h2>
    <p class="brief">本简报优先呈现近期发表且与当前研究方向相关的文献。每篇文献提供中英文标题、见刊日期、内容摘要、研究相关性及原文入口，便于快速判断是否需要进一步阅读。</p>
  </div>
  <div class="section">
    <h2>文献索引</h2>
    <ol class="toc">
"""

    for index, paper in enumerate(papers, 1):
        title_cn = paper.get("title_cn") or paper.get("title") or "标题信息待补充"
        anchor = f"paper-{index}"
        html += f"""      <li><span class="date">{esc(clean_date(paper.get('publication_date')))}</span><a href="#{anchor}">{esc(title_cn)}</a></li>
"""

    html += """    </ol>
  </div>
"""

    for index, paper in enumerate(papers, 1):
        title_en = paper.get("title_en") or paper.get("title") or ""
        title_cn = paper.get("title_cn") or "中文标题待补充"
        summary = short_text(paper.get("summary_cn_short"), "该文献摘要信息尚未完成结构化处理，可展开查看完整摘要或通过原文链接进一步阅读。")
        relevance = short_text(paper.get("relevance_cn"), "该文献与当前研究方向的具体关联仍需人工进一步判断。")
        abstract_cn = paper.get("abstract_cn") or ""
        abstract_en = paper.get("abstract") or ""
        link = paper.get("url") or (f"https://doi.org/{paper.get('doi')}" if paper.get("doi") else "")
        tags = "".join(f'<span class="tag">{esc(tag)}</span>' for tag in topic_tags(paper))
        details = ""
        if abstract_cn and abstract_cn != "[翻译失败]":
            details += f"""<details><summary>展开完整中文摘要</summary><div class="abstract">{esc(abstract_cn)}</div></details>"""
        if abstract_en:
            details += f"""<details><summary>展开英文摘要</summary><div class="abstract">{esc(abstract_en)}</div></details>"""
        action = f'<a class="button" href="{esc(link)}" target="_blank">查看原文</a>' if link else ""

        html += f"""  <article class="card" id="paper-{index}">
    <div class="card-head">
      <div class="index">{index:02d}</div>
      <div class="date-line">见刊日期：{esc(clean_date(paper.get('publication_date')))}</div>
      <div class="title-cn">{esc(title_cn)}</div>
      <div class="title-en">{esc(title_en)}</div>
    </div>
    <div class="meta">
      <div>期刊信息：{esc(journal_label(paper))}</div>
      <div class="tags">研究方向：{tags or '<span class="tag">待分类</span>'}</div>
    </div>
    <div class="body">
      <div class="label">内容摘要</div>
      <div class="text">{esc(summary)}</div>
      <div class="relevance">
        <div class="label">与当前研究的相关性</div>
        <div class="text" style="margin-bottom:0">{esc(relevance)}</div>
      </div>
      <div class="actions">{action}</div>
      {details}
    </div>
  </article>
"""

    html += f"""  <div class="footer">
    生成时间：{today.strftime("%Y-%m-%d %H:%M")} · 数据来源：OpenAlex · 结构化摘要由自动化流程生成
  </div>
</div>
</body>
</html>
"""
    return html


def main():
    log.info("=" * 40)
    log.info("HTML 文献简报生成")
    log.info("=" * 40)
    data, source_path = load_latest_data()
    log.info("加载 %s 篇论文: %s", len(data.get("papers", [])), os.path.basename(source_path))
    html = gen_html(data)
    today = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(OUTPUT_DIR, f"daily_report_{today}.html")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(html)
    log.info("已保存: %s", path)
    print(f"[OK] HTML -> {path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as error:
        log.error("失败: %s", error)
        import traceback
        traceback.print_exc()
        sys.exit(1)
