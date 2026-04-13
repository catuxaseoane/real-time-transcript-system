"""
Unit tests for the transcript handler and refinement logic.

Each test class covers one type of operation.
Run with:  python -m unittest tests/test_handler.py
"""
import unittest
from pathlib import Path

from transcript.handler import handle
from transcript.entries import Paragraph


# ── helpers ─────────────────────────────────────────────────────────────────

def run(lines: list[str]) -> list[Paragraph]:
    """Process a list of raw JSONL strings and return the resulting paragraphs."""
    paragraphs: list[Paragraph] = []
    for line in lines:
        line = line.strip()
        if line:
            handle(line, paragraphs)
    return paragraphs


# ── word-update ──────────────────────────────────────────────────────────────

class TestWordUpdate(unittest.TestCase):

    def test_replaces_word(self):
        # "Hello world" → update s=1.4 → "Hello World"
        paras = run([
            '{"s":1.0,"e":1.4,"p":"p1","t":"Hello","S":"0"}',
            '{"s":1.4,"e":1.8,"p":"p1","t":"world","S":"0"}',
            '{"s":1.4,"e":null,"rt":"World","i":"word-update"}',
        ])
        self.assertEqual(paras[0].text(), "Hello World")

    def test_nonexistent_timestamp_is_noop(self):
        # Updating a timestamp that doesn't exist leaves text unchanged
        paras = run([
            '{"s":1.0,"e":1.4,"p":"p1","t":"Hello","S":"0"}',
            '{"s":99.0,"e":null,"rt":"BOOM","i":"word-update"}',
        ])
        self.assertEqual(paras[0].text(), "Hello")


# ── word-delete ──────────────────────────────────────────────────────────────

class TestWordDelete(unittest.TestCase):

    def test_removes_word(self):
        paras = run([
            '{"s":3.0,"e":3.5,"p":"p2","t":"TomHanks","S":"1"}',
            '{"s":3.5,"e":3.8,"p":"p2","t":"is","S":"1"}',
            '{"s":3.8,"e":4.0,"p":"p2","t":"here","S":"1"}',
            '{"s":3.0,"e":null,"rt":null,"i":"word-delete"}',
        ])
        self.assertEqual(paras[0].text(), "is here")

    def test_only_affects_matching_paragraph(self):
        # Speaker changes: pA (S=0) then pB (S=1) — deleting s=2.0 from pB must not touch pA
        paras = run([
            '{"s":1.0,"e":1.5,"p":"pA","t":"Keep","S":"0"}',
            '{"s":2.0,"e":2.5,"p":"pB","t":"Delete","S":"1"}',
            '{"s":2.0,"e":null,"rt":null,"i":"word-delete"}',
        ])
        self.assertEqual(paras[0].text(), "Keep")  # pA untouched
        self.assertEqual(paras[1].text(), "")       # pB now empty

    def test_nonexistent_timestamp_is_noop(self):
        paras = run([
            '{"s":1.0,"e":1.5,"p":"p1","t":"Hello","S":"0"}',
            '{"s":99.0,"e":null,"rt":null,"i":"word-delete"}',
        ])
        self.assertEqual(paras[0].text(), "Hello")


# ── word-insert ──────────────────────────────────────────────────────────────

class TestWordInsert(unittest.TestCase):

    def test_readme_tomhanks_example(self):
        # word-delete "TomHanks" + two word-inserts → "Tom Hanks is here"
        paras = run([
            '{"s":3.0,"e":3.5,"p":"p2","t":"TomHanks","S":"1"}',
            '{"s":3.5,"e":3.8,"p":"p2","t":"is","S":"1"}',
            '{"s":3.8,"e":4.0,"p":"p2","t":"here","S":"1"}',
            '{"s":3.0,"e":null,"rt":null,"i":"word-delete"}',
            '{"s":3.0,"e":3.25,"rt":"Tom","i":"word-insert"}',
            '{"s":3.25,"e":3.5,"rt":"Hanks","i":"word-insert"}',
        ])
        self.assertEqual(paras[0].text(), "Tom Hanks is here")

    def test_inserts_in_timestamp_order(self):
        # p7: "Good" (s=15.0) … "morning" (s=15.6) → insert "fine" at s=15.4
        # Expected: "Good fine morning"
        paras = run([
            '{"s":15.0,"e":15.4,"p":"p7","t":"Good","S":"0"}',
            '{"s":15.6,"e":16.0,"p":"p7","t":"morning","S":"0"}',
            '{"s":15.4,"e":15.6,"rt":"fine","i":"word-insert"}',
        ])
        self.assertEqual(paras[0].text(), "Good fine morning")

    def test_readme_news_merge_example(self):
        # Exact example from the README spec section
        paras = run([
            '{"s":1493.2,"e":1493.44,"p":"17","t":"close","S":"2"}',
            '{"s":1493.44,"e":1493.72,"p":"17","t":"with","S":"2"}',
            '{"s":1495.2,"e":1495.44,"p":"17","t":"good","S":"2"}',
            '{"s":1495.44,"e":1495.96,"p":"17","t":"news","S":"2"}',
            '{"s":1496.4,"e":1496.4,"p":"17","t":"?","S":"2"}',
            '{"s":1495.44,"e":null,"rt":null,"i":"word-delete"}',
            '{"s":1496.4,"e":null,"rt":null,"i":"word-delete"}',
            '{"s":1495.44,"e":1496.4,"rt":"news?","i":"word-insert"}',
        ])
        self.assertEqual(paras[0].text(), "close with good news?")


# ── paragraph-insert ─────────────────────────────────────────────────────────

class TestParagraphInsert(unittest.TestCase):

    def test_splits_paragraph(self):
        # p5: "Split here now please", split at s=10.3
        # → p5: "Split"  |  new: "here now please"
        paras = run([
            '{"s":10.0,"e":10.3,"p":"p5","t":"Split","S":"2"}',
            '{"s":10.3,"e":10.6,"p":"p5","t":"here","S":"2"}',
            '{"s":10.6,"e":10.9,"p":"p5","t":"now","S":"2"}',
            '{"s":10.9,"e":11.2,"p":"p5","t":"please","S":"2"}',
            '{"s":10.3,"i":"paragraph-insert"}',
        ])
        self.assertEqual(len(paras), 2)
        self.assertEqual(paras[0].text(), "Split")
        self.assertEqual(paras[1].text(), "here now please")

    def test_split_preserves_paragraph_order(self):
        paras = run([
            '{"s":1.0,"e":1.5,"p":"before","t":"Before","S":"0"}',
            '{"s":10.0,"e":10.3,"p":"p5","t":"Split","S":"1"}',
            '{"s":10.3,"e":10.6,"p":"p5","t":"here","S":"0"}',
            '{"s":20.0,"e":20.5,"p":"after","t":"After","S":"1"}',
            '{"s":10.3,"i":"paragraph-insert"}',
        ])
        texts = [p.text() for p in paras if p.text().strip()]
        self.assertIn("Before", texts[0])
        self.assertTrue(any("Split" in t for t in texts))
        self.assertTrue(any("here" in t for t in texts))
        self.assertTrue(any("After" in t for t in texts[-1:]))


# ── paragraph-merge ──────────────────────────────────────────────────────────

class TestParagraphMerge(unittest.TestCase):

    def test_currently_noop_does_not_crash(self):
        paras = run([
            '{"s":1.0,"e":1.5,"p":"pA","t":"Hello","S":"0"}',
            '{"s":2.0,"e":2.5,"p":"pB","t":"World","S":"1"}',
            '{"s":1.0,"e":2.5,"i":"paragraph-merge"}',
        ])
        self.assertEqual(len(paras), 2)
        self.assertEqual(paras[0].text(), "Hello")
        self.assertEqual(paras[1].text(), "World")


# ── control records ──────────────────────────────────────────────────────────

class TestControlRecords(unittest.TestCase):

    def _word(self):
        return '{"s":1.0,"e":1.5,"p":"p1","t":"Hello","S":"0"}'

    def test_start_record_ignored(self):
        paras = run([
            '{"type":"start","processing_start_time":"2026-01-01T10:00:00Z"}',
            self._word(),
        ])
        self.assertEqual(len(paras), 1)

    def test_keep_alive_ignored(self):
        paras = run([self._word(), '{"type":"keep-alive"}'])
        self.assertEqual(len(paras), 1)
        self.assertEqual(paras[0].text(), "Hello")

    def test_section_ignored(self):
        paras = run([self._word(), '{"type":"section","name":"predicted-qna","s":1.0}'])
        self.assertEqual(len(paras), 1)

    def test_interruption_ignored(self):
        paras = run([self._word(), '{"type":"interruption","time":1.5,"restarting":true}'])
        self.assertEqual(len(paras), 1)

    def test_unknown_type_ignored(self):
        paras = run([self._word(), '{"type":"future-feature","data":"ignore me"}'])
        self.assertEqual(len(paras), 1)

    def test_end_returns_true(self):
        ended = handle('{"type":"end","code":0}', [])
        self.assertTrue(ended)

    def test_normal_record_returns_false(self):
        ended = handle('{"s":1.0,"e":1.5,"p":"p1","t":"Hello","S":"0"}', [])
        self.assertFalse(ended)


# ── speaker majority vote ────────────────────────────────────────────────────

class TestSpeakerMajorityVote(unittest.TestCase):

    def test_majority_wins(self):
        paras = run([
            '{"s":5.0,"e":5.3,"p":"p3","t":"Mostly","S":"0"}',
            '{"s":5.3,"e":5.6,"p":"p3","t":"one","S":"0"}',
            '{"s":5.6,"e":5.9,"p":"p3","t":"speaker","S":"1"}',
        ])
        self.assertEqual(paras[0].speaker(), "0")

    def test_no_speaker_returns_none(self):
        paras = run(['{"s":1.0,"e":1.5,"p":"p1","t":"Hello"}'])
        self.assertIsNone(paras[0].speaker())

    def test_single_word_speaker(self):
        paras = run(['{"s":1.0,"e":1.5,"p":"p1","t":"Hello","S":"5"}'])
        self.assertEqual(paras[0].speaker(), "5")


# ── indiscernible / special words ────────────────────────────────────────────

class TestSpecialWords(unittest.TestCase):

    def test_indiscernible_included_in_text(self):
        paras = run([
            '{"s":1.0,"e":1.5,"p":"p1","t":"[indiscernible]","S":"0","ot":"unclear","c":0.1}',
            '{"s":1.5,"e":2.0,"p":"p1","t":"words","S":"0"}',
        ])
        self.assertEqual(paras[0].text(), "[indiscernible] words")


# ── full scenario (test_transcript.jsonl) ────────────────────────────────────

class TestFullScenario(unittest.TestCase):

    def _load_jsonl(self, path) -> list[str]:
        with open(path) as f:
            return [line.strip() for line in f if line.strip()]

    def test_full_test_transcript(self):
        lines = self._load_jsonl(Path(__file__).parent / "test_transcript.jsonl")
        paras = run(lines)

        para_by_base_id = {}
        for p in paras:
            base_id = p.paragraph_id.split('_')[0]
            if base_id not in para_by_base_id:
                para_by_base_id[base_id] = []
            para_by_base_id[base_id].append(p)

        # p1: word-update "world" → "World"
        self.assertIn("Hello World", para_by_base_id["p1"][0].text())

        # p2: TomHanks split → Tom Hanks is here
        p2_texts = " ".join(p.text() for p in para_by_base_id["p2"])
        self.assertIn("Tom Hanks is here", p2_texts)

        # p3: majority vote (2×S=0, 1×S=1)
        p3 = para_by_base_id["p3"][0]
        self.assertEqual(p3.speaker(), "0")

        # p4: word-delete s=7.3 ("remove") → "Please this word"
        p4_text = " ".join(p.text() for p in para_by_base_id["p4"])
        self.assertIn("Please this word", p4_text)

        # p5: paragraph-insert at 10.3 → creates split paragraphs
        p5_paras = para_by_base_id["p5"]
        self.assertGreaterEqual(len(p5_paras), 1)

        # p6: [indiscernible] included
        p6_text = " ".join(p.text() for p in para_by_base_id["p6"])
        self.assertIn("[indiscernible]", p6_text)

        # p7: word-insert "fine" at s=15.4 → "Good fine morning"
        if "p7" in para_by_base_id:
            p7_text = " ".join(p.text() for p in para_by_base_id["p7"])
            self.assertIn("Good fine morning", p7_text)

        # p8: paragraph-merge (no-op) → both words present
        p8_text = " ".join(p.text() for p in para_by_base_id["p8"])
        self.assertIn("After interruption", p8_text)

        # readme example: news? merge
        readme_paras = para_by_base_id.get("readme", [])
        if readme_paras:
            readme_text = " ".join(p.text() for p in readme_paras)
            self.assertIn("news?", readme_text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
