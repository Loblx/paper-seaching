#!/usr/bin/env python3
"""Daily literature digest for electrochemical alkene epoxidation research."""
import argparse
import html
import json
import logging
import os
import smtplib
import sys
import time
from datetime import date, datetime, timedelta
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path

import requests

TASK_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = TASK_DIR / "output"
HISTORY_FILE = TASK_DIR / "data" / "paper-history.json"
OPENALEX_WORKS = "https://api.openalex.org/works"
RECENT_DAYS = 60
BACKFILL_DAYS = 365
HISTORY_DAYS = 365
MAX_PAPERS = 8
RECIPIENT = "256677584@qq.com"

PRIMARY_TOPICS = {
    "烯烃环氧化": ("alkene epoxidation", "olefin epoxidation", "electrochemical epoxidation"),
    "氧原子转移": ("oxygen atom transfer", "oxygen-atom transfer", "oxo transfer"),
}
MECHANISTIC_TOPICS = {
    "电催化": ("electrocatalysis", "electrocatalytic", "electrochemical catalysis"),
    "阳离子效应": ("cation effect", "cation-dependent", "alkali cation"),
    "金属-载体相互作用": ("metal-support interaction", "metal support interaction", "strong metal support interaction"),
    "自由基中间体": ("radical intermediate", "radical pathway", "radical mechanism"),
    "界面电场": ("interfacial electric field", "electric field", "interfacial field"),
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "paper-seaching-alkene-epoxidation/1.0", "Accept": "application/json"})


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


def matches_query(work):
    title = (work.get("title") or "").lower()
    text = f"{title} {abstract(work)}".lower()
    # Require a transformation anchor in the title, while allowing the exact
    # Boolean target phrase to occur in the title or abstract. This avoids
    # broad catalysis reviews but retains papers titled "oxidation of alkenes".
    title_anchors = ("alkene", "olefin", "epoxidation", "oxygen atom transfer", "oxygen-atom transfer")
    return bool(any(anchor in title for anchor in title_anchors) and topic_hits(text, PRIMARY_TOPICS) and topic_hits(text, MECHANISTIC_TOPICS))


def load_history(today):
    cutoff = today - timedelta(days=HISTORY_DAYS)
    history = read_json(HISTORY_FILE, {"papers": []})
    papers = []
    for item in history.get("papers", []):
        try:
            if date.fromisoformat(item["sent_on"]) >= cutoff:
                papers.append(item)
        except (KeyError, ValueError):
            pass
    return papers


def openalex(query, start, end):
    filters = ",".join((
        f"from_publication_date:{start.isoformat()}",
        f"to_publication_date:{end.isoformat()}",
        "type:article|preprint",
    ))
    response = SESSION.get(OPENALEX_WORKS, params={
        "search": query, "filter": filters, "sort": "publication_date:desc", "per-page": 30,
        "select": "id,doi,title,publication_date,authorships,primary_location,abstract_inverted_index,cited_by_count",
    }, timeout=30)
    response.raise_for_status()
    return response.json().get("results", [])


def fetch_candidates(today, sent_ids):
    candidates = {}
    # One canonical phrase from each logical clause is used for retrieval;
    # all synonyms are still applied afterwards by matches_query().
    queries = [
        f"{primary_terms[0]} {modifier_terms[0]}"
        for primary_terms in PRIMARY_TOPICS.values()
        for modifier_terms in MECHANISTIC_TOPICS.values()
    ]

    def collect(start):
        for query in queries:
            try:
                works = openalex(query, start, today)
            except requests.RequestException as error:
                log.warning("OpenAlex failed for %s: %s", query, error)
                continue
            log.info("%s -> %s results", query[:64], len(works))
            for work in works:
                key = normalized_id(work)
                if key in sent_ids or not work.get("title") or not abstract(work) or not matches_query(work):
                    continue
                candidates[key] = work

    collect(today - timedelta(days=RECENT_DAYS))
    if len(candidates) < MAX_PAPERS:
        log.info("Only %s unseen recent candidates; backfilling one year.", len(candidates))
        collect(today - timedelta(days=BACKFILL_DAYS))
    return candidates


def score(work, today):
    text = f"{work.get('title', '')} {abstract(work)}".lower()
    primary = len(topic_hits(text, PRIMARY_TOPICS))
    mechanism = len(topic_hits(text, MECHANISTIC_TOPICS))
    try:
        age = (today - date.fromisoformat(work.get("publication_date") or "")).days
    except ValueError:
        age = BACKFILL_DAYS
    recency = max(0, 50 - 50 * age / BACKFILL_DAYS)
    return primary * 30 + mechanism * 18 + recency + min((work.get("cited_by_count") or 0) / 100, 2)


def select(candidates, today):
    selected, topic_count = [], {}
    for work in sorted(candidates.values(), key=lambda item: score(item, today), reverse=True):
        text = f"{work.get('title', '')} {abstract(work)}".lower()
        tags = topic_hits(text, MECHANISTIC_TOPICS)
        if len(selected) >= MAX_PAPERS or (tags and all(topic_count.get(tag, 0) >= 3 for tag in tags)):
            continue
        selected.append(work)
        for tag in tags:
            topic_count[tag] = topic_count.get(tag, 0) + 1
    return selected


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
        text = f"{paper.get('title', '')} {abstract(paper)}".lower()
        tags = topic_hits(text, PRIMARY_TOPICS) + topic_hits(text, MECHANISTIC_TOPICS)
        cards.append(f"""<article><h2>{number}. {html.escape(paper['title'])}</h2>
<p class=meta>{html.escape(paper.get('publication_date') or '日期待定')} · {html.escape(authors(paper))}</p>
<p>{html.escape(abstract(paper))}</p><p class=tags>{' · '.join(html.escape(tag) for tag in tags)}</p>
<a href=\"{html.escape(link(paper))}\">查看原文 ↗</a></article>""")
    return f"""<!doctype html><html lang=zh-CN><meta charset=utf-8><meta name=viewport content=\"width=device-width,initial-scale=1\">
<title>烯烃环氧化与氧原子转移文献简报</title><style>body{{font-family:Arial,'Microsoft YaHei',sans-serif;margin:auto;max-width:820px;background:#f4f7fb;color:#182334;padding:18px;line-height:1.6}}header,article{{background:white;border-radius:12px;padding:18px;margin-bottom:14px;box-shadow:0 1px 3px #ccd}}h1{{margin:0;color:#005b96}}h2{{font-size:18px;margin:0 0 8px}}.meta{{color:#586575;font-size:13px}}.tags{{color:#005b96;font-weight:bold;font-size:13px}}a{{color:#006fb8}}</style>
<header><h1>烯烃环氧化与氧原子转移文献简报</h1><p>检索式：("alkene epoxidation" OR "oxygen atom transfer") AND（电催化、阳离子效应、金属-载体相互作用、自由基中间体或界面电场）</p><p>生成时间：{generated_at.strftime('%Y-%m-%d %H:%M')}</p></header>{''.join(cards) or '<article>本次未找到符合时效与去重要求的文献。</article>'}</html>"""


def send_email(report, papers, date_tag, dry_run):
    sender, auth_code = os.getenv("QQ_EMAIL", ""), os.getenv("QQ_EMAIL_AUTH_CODE", "")
    if dry_run:
        log.info("Dry run: email not sent to %s", RECIPIENT)
        return True
    if not sender or not auth_code:
        raise RuntimeError("QQ_EMAIL or QQ_EMAIL_AUTH_CODE is missing")
    message = MIMEMultipart("alternative")
    message["From"] = formataddr((str(Header("烯烃环氧化文献简报", "utf-8")), sender))
    message["To"] = RECIPIENT
    message["Subject"] = Header(f"[每日文献] 烯烃环氧化与氧原子转移 {date_tag}", "utf-8")
    plain = f"本期筛选 {len(papers)} 篇文献。请使用支持 HTML 的邮件客户端查看完整简报。"
    message.attach(MIMEText(plain, "plain", "utf-8"))
    message.attach(MIMEText(report, "html", "utf-8"))
    with smtplib.SMTP("smtp.qq.com", 587, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(sender, auth_code)
        smtp.sendmail(sender, [RECIPIENT], message.as_string())
    log.info("Digest sent to %s", RECIPIENT)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Generate a report but do not send email.")
    args = parser.parse_args()
    today = date.today()
    history = load_history(today)
    candidates = fetch_candidates(today, {item["key"] for item in history if item.get("key")})
    papers = select(candidates, today)
    now = datetime.now()
    report = digest_html(papers, now)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT_DIR / f"alkene-epoxidation-digest-{today.isoformat()}.html"
    report_path.write_text(report, encoding="utf-8")
    send_email(report, papers, today.isoformat(), args.dry_run)
    if not args.dry_run:
        history.extend({"key": normalized_id(paper), "sent_on": today.isoformat(), "title": paper["title"]} for paper in papers)
        write_json(HISTORY_FILE, {"updated_at": now.isoformat(), "papers": history})
    print(f"[OK] selected={len(papers)} report={report_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        log.error("Task failed: %s", error)
        sys.exit(1)
