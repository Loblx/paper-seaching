#!/usr/bin/env python3
"""Generate a recent, non-repeating literature brief for the research program."""
import json
import logging
import os
import re
import sys
import time
import traceback
from datetime import date, datetime, timedelta

import requests

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(WORK_DIR, "output")
JOURNALS_DB = os.path.join(WORK_DIR, "journals_db.json")
HISTORY_PATH = os.path.join(WORK_DIR, "data", "paper_history.json")
OA_BASE = "https://api.openalex.org"
API_DELAY = 0.3
RECENT_WINDOW_DAYS = 45
BACKFILL_WINDOW_DAYS = 365
HISTORY_RETENTION_DAYS = 365
MAX_PAPERS = 10

# The user's research topics: target natural products, fungal P450/CPR,
# yeast chassis cells, selectivity, and AI-assisted enzyme engineering.
SEARCH_TOPICS = [
    ("目标产物", "pleuromutilin biosynthesis cytochrome P450"),
    ("目标产物", "pleuromutilin biosynthesis enzyme engineering"),
    ("目标产物", "taxol paclitaxel biosynthesis cytochrome P450"),
    ("真菌P450", "fungal diterpene biosynthesis cytochrome P450"),
    ("真菌P450", "basidiomycete natural product biosynthesis P450"),
    ("P450/CPR", "cytochrome P450 reductase CPR coupling biocatalysis"),
    ("选择性", "P450 regioselectivity stereoselectivity enzyme engineering"),
    ("酵母底盘", "Saccharomyces cerevisiae metabolic engineering P450"),
    ("酵母底盘", "Yarrowia lipolytica metabolic engineering P450"),
    ("AI酶工程", "P450 machine learning protein engineering"),
    ("AI酶工程", "protein language model enzyme engineering P450"),
]

PROJECT_KEYWORDS = [
    "pleuromutilin", "taxol", "paclitaxel", "cytochrome p450", "p450", "cyp",
    "cytochrome p450 reductase", "monooxygenase", "hydroxylation", "oxidation",
    "diterpene", "terpene biosynthesis", "basidiomycete", "mushroom", "fungal",
    "saccharomyces", "yarrowia", "metabolic engineering", "chassis cell",
    "regioselectivity", "stereoselectivity", "substrate specificity", "enzyme engineering",
]
AI_KEYWORDS = [
    "machine learning", "deep learning", "protein language model", "language model",
    "directed evolution", "protein engineering", "protein design", "computational design",
]
EXCLUDE_KEYWORDS = [
    "large language model", "chatgpt", "medical image", "image segmentation",
    "clinical trial", "patient", "neuroinflammation", "social media",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)
_session = requests.Session()
_session.headers.update({"User-Agent": "PaperSeaching/3.0", "Accept": "application/json"})
_last_call = 0.0


def _rl():
    global _last_call
    elapsed = time.time() - _last_call
    if elapsed < API_DELAY:
        time.sleep(API_DELAY - elapsed)
    _last_call = time.time()


def oa_get(url, params, retries=3):
    for attempt in range(retries):
        _rl()
        try:
            response = _session.get(url, params=params, timeout=20)
            if response.status_code == 429:
                wait = (attempt + 1) * 5
                log.warning("OpenAlex rate limited; waiting %ss", wait)
                time.sleep(wait)
                continue
            response.raise_for_status()
            return response.json()
        except Exception as error:
            log.warning("OpenAlex request failed (%s/%s): %s", attempt + 1, retries, error)
            time.sleep(2 * (attempt + 1))
    return None


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as error:
        log.warning("Invalid JSON in %s: %s", path, error)
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def load_journals_db():
    db = load_json(JOURNALS_DB, [])
    log.info("Journal database: %s entries", len(db))
    return db


def load_history(today):
    history = load_json(HISTORY_PATH, {"papers": []})
    cutoff = today - timedelta(days=HISTORY_RETENTION_DAYS)
    kept = []
    for item in history.get("papers", []):
        try:
            if date.fromisoformat(item["sent_on"]) >= cutoff:
                kept.append(item)
        except (KeyError, ValueError):
            continue
    return kept


def stable_key(work):
    doi = (work.get("doi") or "").lower().replace("https://doi.org/", "")
    if doi:
        return f"doi:{doi}"
    work_id = work.get("id") or ""
    if work_id:
        return f"id:{work_id}"
    title = re.sub(r"\W+", "", (work.get("title") or "").lower())
    return f"title:{title}"


def reconstruct_abstract(index):
    if not index:
        return ""
    words = [(position, word) for word, positions in index.items() for position in positions]
    return " ".join(word for _, word in sorted(words))


def is_relevant(title, abstract):
    """Require a direct connection to the user's research program."""
    text = f"{title} {abstract}".lower()
    if any(word in text for word in EXCLUDE_KEYWORDS) and not any(word in text for word in PROJECT_KEYWORDS):
        return False
    project_matches = sum(word in text for word in PROJECT_KEYWORDS)
    has_p450_or_target = any(word in text for word in PROJECT_KEYWORDS[:13])
    has_ai = any(word in text for word in AI_KEYWORDS)
    return project_matches >= 2 or (has_p450_or_target and has_ai)


def search_works(query, start_date, end_date, limit=30):
    filters = ",".join([
        f"from_publication_date:{start_date.isoformat()}",
        f"to_publication_date:{end_date.isoformat()}",
        "type:article|preprint",
    ])
    data = oa_get(f"{OA_BASE}/works", {
        "search": query,
        "sort": "publication_date:desc",
        "per-page": min(limit, 50),
        "filter": filters,
        "select": "id,doi,title,authorships,primary_location,publication_date,publication_year,abstract_inverted_index,concepts,cited_by_count,language",
    })
    results = data.get("results", []) if data else []
    log.info("  %s (%s to %s) -> %s", query[:42], start_date, end_date, len(results))
    return results


def get_venue(primary_location):
    source = (primary_location or {}).get("source") if isinstance(primary_location, dict) else None
    return source.get("display_name", "") if source else ""


def lookup_journal(venue, db):
    venue = (venue or "").strip().lower()
    for journal in db:
        for name in [journal["name"]] + journal.get("aliases", []):
            name = name.lower()
            if venue and (name == venue or name in venue or venue in name):
                return {"name": journal["name"], "if": journal["if"], "cas_rank": journal["cas_rank"]}
    return None


def score_work(work, categories, today):
    text = f"{work.get('title', '')} {reconstruct_abstract(work.get('abstract_inverted_index'))}".lower()
    project_score = 10 * sum(keyword in text for keyword in PROJECT_KEYWORDS)
    ai_score = 5 * sum(keyword in text for keyword in AI_KEYWORDS)
    publication_date = work.get("publication_date") or ""
    try:
        age = (today - date.fromisoformat(publication_date)).days
    except ValueError:
        age = BACKFILL_WINDOW_DAYS
    recency_score = max(0, 60 - age * 60 / BACKFILL_WINDOW_DAYS)
    category_bonus = 5 * len(categories)
    citation_tiebreaker = min((work.get("cited_by_count") or 0) / 100, 2)
    return project_score + ai_score + recency_score + category_bonus + citation_tiebreaker


def build_entry(work, db, categories):
    venue = get_venue(work.get("primary_location"))
    publication_date = work.get("publication_date") or ""
    doi = (work.get("doi") or "").replace("https://doi.org/", "")
    authors = [a.get("author", {}).get("display_name", "") for a in work.get("authorships") or []]
    authors = [name for name in authors if name]
    concepts = sorted(work.get("concepts") or [], key=lambda item: item.get("score", 0), reverse=True)
    return {
        "id": work.get("id", ""), "title": work.get("title", "N/A"), "doi": doi,
        "url": f"https://doi.org/{doi}" if doi else work.get("id", ""),
        "abstract": reconstruct_abstract(work.get("abstract_inverted_index")),
        "authors": authors,
        "authors_short": ", ".join(authors[:5]) + (" et al." if len(authors) > 5 else ""),
        "venue": venue, "journal_info": lookup_journal(venue, db),
        "publication_date": publication_date, "year": publication_date[:4], "month": publication_date[5:7],
        "citations": work.get("cited_by_count") or 0,
        "concepts": [item.get("display_name", "") for item in concepts[:3]],
        "research_topics": sorted(categories), "source": "OpenAlex",
    }


def main():
    today = date.today()
    recent_start = today - timedelta(days=RECENT_WINDOW_DAYS)
    db = load_journals_db()
    history = load_history(today)
    sent_keys = {item["key"] for item in history if item.get("key")}
    candidates = {}

    def collect(start_date):
        for category, query in SEARCH_TOPICS:
            for work in search_works(query, start_date, today):
                key = stable_key(work)
                title = (work.get("title") or "").strip()
                abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
                if not title or not abstract or key in sent_keys or not is_relevant(title, abstract):
                    continue
                record = candidates.setdefault(key, {"work": work, "categories": set()})
                record["categories"].add(category)

    collect(recent_start)
    if len(candidates) < MAX_PAPERS:
        log.info("Only %s unseen recent papers; backfilling to %s days.", len(candidates), BACKFILL_WINDOW_DAYS)
        collect(today - timedelta(days=BACKFILL_WINDOW_DAYS))

    ranked = sorted(
        candidates.values(),
        key=lambda item: score_work(item["work"], item["categories"], today),
        reverse=True,
    )
    selected = []
    category_counts = {}
    for item in ranked:
        categories = item["categories"]
        if len(selected) >= MAX_PAPERS:
            break
        # Keep one dominant topic from taking over the entire brief.
        if all(category_counts.get(category, 0) >= 3 for category in categories):
            continue
        selected.append(item)
        for category in categories:
            category_counts[category] = category_counts.get(category, 0) + 1

    entries = [build_entry(item["work"], db, item["categories"]) for item in selected]
    save_json(os.path.join(OUTPUT_DIR, f"papers_raw_{today.isoformat()}.json"), {
        "generated_at": datetime.now().isoformat(),
        "total_works": len(candidates), "papers": entries,
        "search_window": {"recent_days": RECENT_WINDOW_DAYS, "max_backfill_days": BACKFILL_WINDOW_DAYS},
    })
    history.extend({"key": stable_key(item["work"]), "sent_on": today.isoformat(), "title": item["work"].get("title", "")} for item in selected)
    save_json(HISTORY_PATH, {"updated_at": datetime.now().isoformat(), "papers": history})
    log.info("Selected %s unseen papers from %s candidates; categories: %s", len(entries), len(candidates), category_counts)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as error:
        log.error("Failed: %s", error)
        traceback.print_exc()
        sys.exit(1)
