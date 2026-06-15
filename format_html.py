#!/usr/bin/env python3
"""format_html.py — 从翻译后的 JSON 生成精美 HTML 日报页面"""

import json, logging, os, sys
from datetime import datetime

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(WORK_DIR, "output")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)


def load_latest_data():
    """优先加载 papers_translated_*.json，回退到 papers_raw_*.json"""
    for prefix in ["papers_translated_", "papers_raw_"]:
        fs = [f for f in os.listdir(OUTPUT_DIR) if f.startswith(prefix) and f.endswith(".json")]
        if fs:
            p = os.path.join(OUTPUT_DIR, max(fs))
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f), p
    log.error("未找到数据文件")
    sys.exit(1)


def gen_recommendation(paper):
    """生成推荐理由（与旧版 format_daily_list.py 逻辑兼容）"""
    txt = ((paper.get("title") or "") + " " + (paper.get("abstract") or "")).lower()
    ji = paper.get("journal_info")

    tags = []
    kw_map = [
        ("deep learning", "深度学习"), ("neural network", "深度学习"),
        ("transformer", "Transformer"), ("language model", "蛋白质语言模型"),
        ("diffusion", "生成式AI"), ("graph neural", "图神经网络"),
        ("reinforcement", "强化学习"), ("directed evolution", "定向进化"),
        ("enzyme design", "酶设计"), ("catalytic", "酶催化"),
        ("protein design", "蛋白质设计"), ("protein structure", "蛋白质结构"),
        ("high-throughput", "高通量筛选"), ("active learning", "主动学习"),
        ("molecular dynamics", "分子动力学"), ("alphafold", "AlphaFold"),
        ("protein engineering", "蛋白质工程"), ("enzyme engineering", "酶工程"),
    ]
    for kw, lb in kw_map:
        if kw in txt:
            tags.append(lb)

    parts = [f"方向：{'、'.join(tags[:3])}"]
    ms = []
    if "pretrained" in txt or "pre-trained" in txt:
        ms.append("预训练模型")
    if "zero-shot" in txt or "few-shot" in txt:
        ms.append("零样本/少样本学习")
    if ms:
        parts.append(f"采用{'、'.join(ms)}等技术")
    ct = paper.get("citations") or 0
    parts.append(f"引用{ct}次" if ct >= 10 else "新近发表")
    parts.append(f"发表于{paper.get('year', '')}年")
    if ji:
        parts.append(f"期刊{ji['name']}（中科院{ji['cas_rank']}，IF={ji['if']}）")
    return "；".join(parts) + "。"


def escape_html(text):
    """转义 HTML 特殊字符"""
    if not text:
        return ""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = text.replace('"', "&quot;").replace("'", "&#39;")
    return text


def gen_html(data):
    """生成完整的 HTML 页面"""
    papers = data.get("papers", [])
    today = datetime.now()
    date_str = today.strftime("%Y年%m月%d日")
    date_tag = today.strftime("%Y-%m-%d")

    total = data.get("total_works", 0)
    translated_count = data.get("translation_stats", {}).get("translated", 0)
    has_translation = any(p.get("abstract_cn") for p in papers if p.get("abstract_cn"))

    # 构建每篇论文的 HTML
    papers_html = []
    for i, p in enumerate(papers, 1):
        title = escape_html(p.get("title", "N/A"))
        url = p.get("url", "")
        doi = p.get("doi", "")
        authors = escape_html(p.get("authors_short", "N/A"))
        abstract_en = escape_html(p.get("abstract", ""))
        abstract_cn = escape_html(p.get("abstract_cn", ""))
        rec = gen_recommendation(p)
        citations = p.get("citations", 0)
        year = p.get("year", "")
        concepts = p.get("concepts", [])
        ji = p.get("journal_info")

        # 期刊信息字符串
        journal_str = ""
        venue = p.get("venue", "")
        if ji:
            journal_str = f"{ji['name']}（中科院{ji['cas_rank']}，IF={ji['if']}）"
        elif venue:
            journal_str = venue

        # 概念标签
        concept_tags = " ".join(
            f'<span class="tag">{escape_html(c)}</span>' for c in concepts[:3]
        )

        # DOI 链接
        doi_html = ""
        if doi:
            doi_html = f'<a href="https://doi.org/{doi}" class="doi-link" target="_blank">DOI: {doi}</a>'

        # 标题链接
        title_html = f'<a href="{url}" target="_blank">{title}</a>' if url else title

        # 引用标签
        cite_badge = f'<span class="cite-badge">引用 {citations}</span>'

        abstracts_html = ""
        if abstract_en:
            abstracts_html += f"""
                <div class="abstract">
                    <div class="abstract-label">英文摘要</div>
                    <p class="abstract-en">{abstract_en}</p>
                </div>"""
        if abstract_cn and abstract_cn not in ("[翻译失败]", ""):
            abstracts_html += f"""
                <div class="abstract">
                    <div class="abstract-label">中文翻译</div>
                    <p class="abstract-cn">{abstract_cn}</p>
                </div>"""

        paper_html = f"""
        <div class="paper-card">
            <div class="paper-number">{i}</div>
            <div class="paper-header">
                <h2 class="paper-title">{title_html}</h2>
                <div class="paper-meta">
                    <span class="meta-item"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>{journal_str}</span>
                    <span class="meta-item"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>{year}</span>
                    <span class="meta-item">{cite_badge}</span>
                </div>
            </div>
            <div class="paper-authors">{authors}</div>
            <div class="paper-concepts">{concept_tags}</div>
            {abstracts_html}
            <div class="paper-rec">
                <div class="rec-label">推荐理由</div>
                <p>{rec}</p>
            </div>
            {f'<div class="paper-doi">{doi_html}</div>' if doi_html else ''}
        </div>"""
        papers_html.append(paper_html)

    papers_section = "\n".join(papers_html)

    # 总览表格行
    table_rows = []
    for i, p in enumerate(papers, 1):
        title = escape_html(p.get("title", "N/A")[:70])
        ji = p.get("journal_info")
        jn = ji["name"] if ji else (p.get("venue", "")[:20] or "N/A")
        table_rows.append(
            f'<tr><td>{i}</td><td class="title-cell">{title}</td><td>{jn}</td><td>{p.get("year", "")}</td><td>{p.get("citations", 0)}</td></tr>'
        )

    table_html = "\n".join(table_rows)

    translation_badge = ""
    if has_translation:
        translation_badge = f'<span class="badge"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg> 已翻译 {translated_count} 篇</span>'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI+酶工程 每日文献速递 {date_tag}</title>
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Noto Sans SC", "Microsoft YaHei", sans-serif;
            background: #f0f4f8; color: #1a2332; line-height: 1.6;
        }}
        .container {{ max-width: 960px; margin: 0 auto; padding: 0 16px; }}

        /* Header */
        .header {{
            background: linear-gradient(135deg, #1a73e8 0%, #1557b0 100%);
            color: #fff; padding: 40px 0 32px; margin-bottom: 24px;
        }}
        .header h1 {{ font-size: 26px; font-weight: 700; margin-bottom: 8px; }}
        .header .subtitle {{ font-size: 14px; opacity: 0.85; }}
        .header .stats {{
            display: flex; gap: 20px; margin-top: 16px; flex-wrap: wrap;
        }}
        .header .stat-item {{
            background: rgba(255,255,255,0.15); border-radius: 8px;
            padding: 8px 16px; font-size: 13px;
        }}
        .header .stat-item strong {{ font-size: 18px; display: block; }}

        /* Overview Table */
        .overview {{
            background: #fff; border-radius: 12px; padding: 20px;
            margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }}
        .overview h2 {{ font-size: 18px; margin-bottom: 12px; color: #1a73e8; }}
        .overview table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
        .overview th {{
            text-align: left; padding: 8px 10px; border-bottom: 2px solid #e8edf3;
            color: #5f6b7a; font-weight: 600; font-size: 12px; text-transform: uppercase;
        }}
        .overview td {{ padding: 8px 10px; border-bottom: 1px solid #eef2f7; vertical-align: top; }}
        .overview .title-cell {{ max-width: 380px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}

        /* Paper Card */
        .paper-card {{
            background: #fff; border-radius: 12px; padding: 24px;
            margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            position: relative; padding-left: 64px;
        }}
        .paper-number {{
            position: absolute; left: 20px; top: 24px;
            width: 32px; height: 32px; background: #1a73e8; color: #fff;
            border-radius: 50%; display: flex; align-items: center;
            justify-content: center; font-weight: 700; font-size: 14px;
        }}
        .paper-title {{ font-size: 17px; margin-bottom: 8px; }}
        .paper-title a {{ color: #1a2332; text-decoration: none; }}
        .paper-title a:hover {{ color: #1a73e8; text-decoration: underline; }}
        .paper-meta {{
            display: flex; gap: 16px; flex-wrap: wrap; align-items: center;
            font-size: 13px; color: #5f6b7a; margin-bottom: 8px;
        }}
        .paper-meta .meta-item {{
            display: inline-flex; align-items: center; gap: 4px;
        }}
        .paper-meta svg {{ flex-shrink: 0; }}
        .cite-badge {{
            background: #e8f0fe; color: #1a73e8; padding: 2px 8px;
            border-radius: 10px; font-weight: 600; font-size: 12px;
        }}
        .paper-authors {{
            font-size: 13px; color: #5f6b7a; margin-bottom: 10px;
        }}
        .paper-concepts {{ margin-bottom: 12px; }}
        .tag {{
            display: inline-block; background: #f0f4f8; color: #4a5568;
            padding: 2px 10px; border-radius: 10px; font-size: 12px;
            margin: 2px 4px 2px 0;
        }}
        .abstract {{
            background: #f8fafc; border-radius: 8px; padding: 12px 16px;
            margin-bottom: 12px; border-left: 3px solid #1a73e8;
        }}
        .abstract-label {{
            font-size: 11px; font-weight: 600; color: #1a73e8;
            text-transform: uppercase; margin-bottom: 4px;
        }}
        .abstract p {{ font-size: 14px; color: #2d3748; line-height: 1.7; }}
        .abstract-cn {{ color: #1a2332 !important; }}
        .paper-rec {{
            background: #fffbeb; border-radius: 8px; padding: 12px 16px;
            margin-bottom: 12px; border-left: 3px solid #f59e0b;
        }}
        .rec-label {{
            font-size: 11px; font-weight: 600; color: #d97706;
            text-transform: uppercase; margin-bottom: 4px;
        }}
        .paper-rec p {{ font-size: 14px; color: #2d3748; }}
        .paper-doi {{ margin-top: 8px; }}
        .doi-link {{
            font-size: 13px; color: #1a73e8; text-decoration: none;
        }}
        .doi-link:hover {{ text-decoration: underline; }}

        /* Footer */
        .footer {{
            text-align: center; padding: 32px 0; color: #8a9aa8;
            font-size: 13px;
        }}
        .badge {{
            display: inline-flex; align-items: center; gap: 4px;
            background: rgba(255,255,255,0.2); border-radius: 10px;
            padding: 4px 12px; font-size: 12px;
        }}

        /* Responsive */
        @media (max-width: 640px) {{
            .paper-card {{ padding: 16px; padding-left: 52px; }}
            .paper-number {{ left: 12px; top: 16px; width: 28px; height: 28px; font-size: 12px; }}
            .paper-title {{ font-size: 15px; }}
            .overview .title-cell {{ max-width: 180px; }}
            .header h1 {{ font-size: 20px; }}
        }}

        /* Print */
        @media print {{
            body {{ background: #fff; }}
            .paper-card, .overview {{ box-shadow: none; border: 1px solid #e0e0e0; }}
            .header {{ background: #1a73e8 !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
            .cite-badge {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="container">
            <h1>📄 AI+酶工程 每日文献速递</h1>
            <div class="subtitle">自动检索 OpenAlex · AI/机器学习 × 酶工程/蛋白质工程 交叉领域最新论文</div>
            <div class="stats">
                <div class="stat-item"><strong>{date_str}</strong>生成日期</div>
                <div class="stat-item"><strong>{total}</strong>检索论文</div>
                <div class="stat-item"><strong>{len(papers)}</strong>精选推荐</div>
                {f'<div class="stat-item"><strong>{translated_count}</strong>已翻译</div>' if has_translation else ''}
            </div>
        </div>
    </div>

    <div class="container">
        <div class="overview">
            <h2>📋 总览</h2>
            <div style="overflow-x: auto;">
                <table>
                    <thead><tr><th>#</th><th>标题</th><th>期刊</th><th>年份</th><th>引用</th></tr></thead>
                    <tbody>{table_html}</tbody>
                </table>
            </div>
        </div>

        {papers_section}

        <div class="footer">
            <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 数据来源: <a href="https://openalex.org/" style="color:#1a73e8" target="_blank">OpenAlex</a></p>
            <p style="margin-top:4px">由 AI+酶工程 每日文献推送系统自动生成</p>
        </div>
    </div>
</body>
</html>"""
    return html


def main():
    log.info("=" * 40)
    log.info("HTML 日报生成")
    log.info("=" * 40)

    data, source_path = load_latest_data()
    log.info(f"加载 {len(data['papers'])} 篇论文，来自 {os.path.basename(source_path)}")

    html = gen_html(data)
    today = datetime.now().strftime("%Y-%m-%d")
    output_path = os.path.join(OUTPUT_DIR, f"daily_report_{today}.html")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    log.info(f"已保存: {output_path}")
    print(f"[OK] HTML -> {output_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as e:
        log.error(f"失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
