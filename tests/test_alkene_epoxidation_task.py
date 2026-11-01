import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location(
    "alkene_task", Path(__file__).parents[1] / "tasks" / "alkene-epoxidation" / "task.py"
)
task = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(task)


def work(title, text):
    return {"id": "https://openalex.org/W1", "title": title, "abstract_inverted_index": {word: [i] for i, word in enumerate(text.split())}}


class AlkeneEpoxidationTaskTests(unittest.TestCase):
    def test_requires_primary_and_mechanistic_topic(self):
        self.assertTrue(task.matches_query(work("Electrocatalytic alkene epoxidation", "radical intermediate")))
        self.assertTrue(task.matches_query(work("Electrochemical oxidation of alkenes", "oxygen atom transfer through a radical intermediate")))
        self.assertFalse(task.matches_query(work("Alkene epoxidation", "catalyst mechanism")))
        self.assertFalse(task.matches_query(work("Electrocatalysis", "cation effect")))

    def test_normalized_id_prefers_doi(self):
        self.assertEqual(task.normalized_id({"doi": "https://doi.org/10.1000/example"}), "doi:10.1000/example")
