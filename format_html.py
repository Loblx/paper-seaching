#!/usr/bin/env python3
"""format_html.py — 手机友好的折叠式 HTML 日报（重写版）"""

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

def esc(text):
    if not text: return ""
    return text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;").replace("'","&#39;")

def gen_html(data):
    papers = data.get("papers", [])
    today = datetime.now()
    date_str = today.strftime("%Y年%m月%d日")
    date_tag = today.strftime("%Y-%m-%d")
    total = data.get("total_works", 0)
    has_trans = any(p.get("abstract_cn") for p in papers if p.get("abstract_cn"))
    trans_count = data.get("translation_stats", {}).get("translated", 0)

    T = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0">
<title>AI+酶工程 每日文献 {date_tag}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:#f4f6f9;color:#1a2332;font-size:15px;line-height:1.5;-webkit-text-size-adjust:100%}}
.hd{{background:linear-gradient(135deg,#1a73e8,#1557b0);color:#fff;padding:28px 16px 20px}}
.hd h1{{font-size:22px;font-weight:700;margin-bottom:4px}}
.hd .sub{{font-size:13px;opacity:.8;margin-bottom:12px}}
.hd .s{{display:flex;gap:12px;flex-wrap:wrap}}
.hd .si{{background:rgba(255,255,255,.15);border-radius:8px;padding:6px 14px;font-size:12px}}
.hd .si b{{font-size:16px;display:block}}
.c{{padding:12px 12px 0}}
.ov{{background:#fff;border-radius:10px;padding:14px;margin-bottom:12px;box-shadow:0 1px 2px rgba(0,0,0,.06)}}
.ov h2{{font-size:15px;color:#1a73e8;margin-bottom:8px}}
.ov .ol{{list-style:none;padding:0;margin:0}}
.ov .ol li{{border-bottom:1px solid #eef2f7;padding:5px 0;font-size:13px;display:flex;gap:6px}}
.ov .ol li .on{{color:#1a73e8;font-weight:600;min-width:24px}}
.ov .ol li .ot{{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.ov .ol li .oj{{color:#5f6b7a;font-size:12px;white-space:nowrap}}
.pc{{background:#fff;border-radius:10px;margin-bottom:8px;box-shadow:0 1px 2px rgba(0,0,0,.06);overflow:hidden}}
.ps{{display:flex;flex-wrap:wrap;gap:4px 10px;padding:12px 14px;cursor:pointer;-webkit-user-select:none;user-select:none;list-style:none}}
.ps::-webkit-details-marker{{display:none}}
.ps .pn{{background:#1a73e8;color:#fff;border-radius:50%;width:24px;height:24px;display:inline-flex;align-items:center;justify-content:center;font-weight:700;font-size:11px;flex-shrink:0}}
.ps .pt{{flex:1 1 calc(100% - 34px);font-size:14px;font-weight:600;color:#1a2332;line-height:1.4}}
.ps .pt a{{color:#1a2332;text-decoration:none}}
.ps .pm{{width:100%;display:flex;flex-wrap:wrap;gap:4px 10px;font-size:11px;color:#5f6b7a;margin-left:34px}}
.ps .pj{{color:#1a73e8}}
.ps .pcite{{background:#e8f0fe;color:#1a73e8;padding:0 6px;border-radius:4px;font-weight:600}}
.pd{{padding:0 14px 14px;border-top:1px solid #eef2f7;padding-top:10px;margin-left:34px}}
.pa{{font-size:12px;color:#5f6b7a;margin-bottom:6px}}
.t{{display:inline-block;background:#eef2f7;color:#4a5568;padding:1px 8px;border-radius:6px;font-size:11px;margin:1px 2px}}
.ab{{background:#f8fafc;border-radius:6px;padding:10px 12px;margin:8px 0;border-left:3px solid #1a73e8}}
.al{{font-size:10px;font-weight:600;color:#1a73e8;margin-bottom:2px}}
.ab p{{font-size:13px;color:#2d3748;line-height:1.6}}
.cn{{border-left-color:#059669}}
.cn .al{{color:#059669}}
.doi{{font-size:12px;color:#1a73e8;text-decoration:none;margin-top:6px;display:inline-block}}
.ft{{text-align:center;padding:16px;color:#8a9aa8;font-size:12px}}
.tb{{display:inline-block;background:rgba(255,255,255,.15);border-radius:6px;padding:3px 10px;font-size:11px}}
@media(prefers-color-scheme:dark){{body{{background:#1a1a2e;color:#e4e4e7}}.pc,.ov{{background:#16213e}}.ps .pt a{{color:#e4e4e7}}.ab{{background:#1a1a2e;border-left-color:#3b82f6}}.ab p{{color:#c4c4c7}}.t{{background:#2a2a3e;color:#a4a4a7}}}}
</style></head>
<body><div class="hd">
<h1>AI+酶工程 每日文献速递</h1>
<div class="sub">自动检索 OpenAlex · AI/机器学习 × 酶工程/蛋白质工程</div>
<div class="s">
<div class="si"><b>{date_str}</b>日期</div>
<div class="si"><b>{total}</b>检索</div>
<div class="si"><b>{len(papers)}</b>精选</div>
{f'<div class="si"><span class="tb">&#x2713; {trans_count}篇已翻译</span></div>' if has_trans else ''}
</div></div>
<div class="c">
<div class="ov"><h2>&#x1F4CB; 总览</h2>
<ol class="ol">'''

    for i, p in enumerate(papers, 1):
        t = esc(p.get("title","N/A")[:55])
        ji = p.get("journal_info")
        jn = esc(ji["name"]) if ji else esc(p.get("venue","")[:15] or "")
        T += f'<li><span class="on">{i}</span><span class="ot">{t}</span><span class="oj">{jn}</span></li>'

    T += '</ol></div>'

    for i, p in enumerate(papers, 1):
        ti = esc(p.get("title","N/A"))
        url = p.get("url","")
        doi = p.get("doi","")
        au = esc(p.get("authors_short","N/A"))
        ab_en = esc(p.get("abstract",""))
        ab_cn = esc(p.get("abstract_cn",""))
        ct = p.get("citations",0)
        yr = p.get("year","")
        ji = p.get("journal_info")
        jn = f"{esc(ji['name'])}（{ji['cas_rank']}，IF={ji['if']}）" if ji else esc(p.get("venue","") or "")
        cs = " ".join(f'<span class="t">{esc(c)}</span>' for c in p.get("concepts",[])[:3])
        ti_l = f'<a href="{url}" target="_blank">{ti}</a>' if url else ti
        doi_h = f' <a href="https://doi.org/{doi}" class="doi" target="_blank">DOI &#x2197;</a>' if doi else ""

        ab_html = ""
        if ab_en:
            ab_html += f'<div class="ab"><div class="al">EN</div><p>{ab_en}</p></div>'
        if ab_cn and ab_cn not in ("[翻译失败]",""):
            ab_html += f'<div class="ab cn"><div class="al">中文</div><p>{ab_cn}</p></div>'

        T += f'''<details class="pc">
<summary class="ps">
<span class="pn">{i}</span>
<span class="pt">{ti_l}</span>
<span class="pm"><span class="pj">{jn}</span><span>|</span><span>{yr}</span><span>|</span><span class="pcite">{ct}次</span></span>
</summary>
<div class="pd">
<div class="pa">{au}</div>
<div class="pcp">{cs}</div>
{ab_html}
{doi_h}
</div>
</details>'''

    T += f'''<div class="ft">
<p>生成: {today.strftime("%Y-%m-%d %H:%M")} | 数据: <a href="https://openalex.org" style="color:#1a73e8">OpenAlex</a></p>
<p style="margin-top:2px">AI+酶工程 每日文献推送</p>
</div></div></body></html>'''
    return T

def main():
    log.info("="*40); log.info("HTML 日报生成(手机版)"); log.info("="*40)
    data, source_path = load_latest_data()
    log.info(f"加载 {len(data['papers'])} 篇论文")
    html = gen_html(data)
    today = datetime.now().strftime("%Y-%m-%d")
    p = os.path.join(OUTPUT_DIR, f"daily_report_{today}.html")
    with open(p, "w", encoding="utf-8") as f: f.write(html)
    log.info(f"已保存: {p}"); print(f"[OK] HTML -> {p}")

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: sys.exit(1)
    except Exception as e: log.error(f"失败: {e}"); import traceback; traceback.print_exc(); sys.exit(1)
