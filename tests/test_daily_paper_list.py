import importlib.util
import json
import os
import tempfile
import unittest
from datetime import date


MODULE_PATH = os.path.join(os.path.dirname(__file__), "..", "daily_paper_list.py")
SPEC = importlib.util.spec_from_file_location("daily_paper_list", MODULE_PATH)
paper_list = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(paper_list)


def work(work_id, title, doi):
    return {
        "id": work_id,
        "doi": f"https://doi.org/{doi}",
        "title": title,
        "publication_date": date.today().isoformat(),
        "abstract_inverted_index": {"P450": [0], "enzyme": [1], "engineering": [2]},
        "authorships": [], "primary_location": {}, "concepts": [], "cited_by_count": 0,
    }


class DailyPaperListTests(unittest.TestCase):
    def test_relevance_requires_project_connection(self):
        self.assertTrue(paper_list.is_relevant("P450 enzyme engineering", "A P450 enzyme engineering study."))
        self.assertFalse(paper_list.is_relevant("Clinical image classifier", "A machine learning patient study."))

    def test_history_excludes_previously_delivered_paper(self):
        with tempfile.TemporaryDirectory() as directory:
            original = (paper_list.OUTPUT_DIR, paper_list.HISTORY_PATH, paper_list.SEARCH_TOPICS, paper_list.search_works)
            try:
                paper_list.OUTPUT_DIR = os.path.join(directory, "output")
                paper_list.HISTORY_PATH = os.path.join(directory, "data", "paper_history.json")
                paper_list.SEARCH_TOPICS = [("P450/CPR", "fixture")]
                seen = work("https://openalex.org/W1", "P450 enzyme engineering one", "seen")
                fresh = work("https://openalex.org/W2", "P450 enzyme engineering two", "fresh")
                os.makedirs(os.path.dirname(paper_list.HISTORY_PATH))
                with open(paper_list.HISTORY_PATH, "w", encoding="utf-8") as handle:
                    json.dump({"papers": [{"key": paper_list.stable_key(seen), "sent_on": date.today().isoformat()}]}, handle)
                paper_list.search_works = lambda *args, **kwargs: [seen, fresh]
                paper_list.main()
                with open(os.path.join(paper_list.OUTPUT_DIR, f"papers_raw_{date.today().isoformat()}.json"), encoding="utf-8") as handle:
                    result = json.load(handle)
                self.assertEqual([paper["doi"] for paper in result["papers"]], ["fresh"])
            finally:
                paper_list.OUTPUT_DIR, paper_list.HISTORY_PATH, paper_list.SEARCH_TOPICS, paper_list.search_works = original


if __name__ == "__main__":
    unittest.main()
