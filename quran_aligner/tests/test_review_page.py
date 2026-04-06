from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from quran_aligner.review_page import write_review_html


class ReviewPageTests(unittest.TestCase):
    def test_writes_expected_controls(self) -> None:
        payload = {
            "title": "Review",
            "surah_number": 13,
            "backend": "fake",
            "normalization_profile": "light",
            "audio": {"relative_path": "sample.mp3", "duration_ms": 10000, "duration_label": "00:10.000"},
            "words": [{"id": 1, "ayah_number": 1, "text": "word", "normalized": "word", "start_ms": 0, "end_ms": 100, "score": 0.9, "confidence": 0.9, "flags": [], "is_suspicious": False}],
            "frame_path": [{"frame_index": 0, "start_ms": 0, "end_ms": 40, "global_unit_index": None, "global_word_index": 0, "score": 0.9}],
            "word_runs": [{"run_index": 0, "global_word_index": 0, "ayah_number": 1, "word_index_in_ayah": 1, "text": "word", "normalized": "word", "start_ms": 0, "end_ms": 100, "score": 0.9, "frame_count": 3}],
            "word_occurrences": [{"global_word_index": 0, "ayah_number": 1, "word_index_in_ayah": 1, "text": "word", "normalized": "word", "visit_count": 1, "total_duration_ms": 100, "intervals": [{"start_ms": 0, "end_ms": 100}]}],
            "ayahs": [{"ayah_number": 1, "start_ms": 0, "end_ms": 100, "words": [{"id": 1, "ayah_number": 1, "text": "word", "normalized": "word", "start_ms": 0, "end_ms": 100, "score": 0.9, "confidence": 0.9, "flags": [], "is_suspicious": False}]}],
            "quality": {"coverage": 1.0, "zero_length_ratio": 0.0, "average_word_score": 0.9, "median_word_score": 0.9, "low_score_ratio": 0.0, "gap_count": 0, "uncovered_gap_ratio": 0.0, "warnings": []},
            "suspicious_words": [],
            "gaps": [],
            "refinement": {"changed_word_count": 0, "total_boundary_shift_ms": 0, "notes": []},
            "decoder": {"mode": "segmental_repair_dp", "bucket_ms": 40, "max_repair_words": 4, "phrase_trace": [{"start_word_index": 0, "end_word_index": 0, "start_bucket": 0, "end_bucket": 3, "repair_width": 1}], "debug": None},
            "summaries": {"worst_words": [], "largest_gaps": [], "lowest_ayahs": []},
            "ui": {"show_suspicious_only": False},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "index.html"
            write_review_html(target, payload)
            html = target.read_text(encoding="utf-8")
            self.assertIn("Play selected", html)
            self.assertIn("Play 1s before", html)
            self.assertIn("alignment-data", html)
            self.assertIn("Show only suspicious words", html)
            self.assertIn("Phrase Trace", html)
            self.assertIn("Word Runs", html)
            self.assertIn("Repeated Occurrences", html)
            self.assertIn("Decoder", html)
            self.assertIn("Zoom in", html)
            self.assertIn("Zoom out", html)
            self.assertIn("Reset zoom", html)
            self.assertIn("comparison-scroll", html)
            self.assertIn("comparison-inner", html)
            self.assertIn("Region Analysis", html)
            self.assertIn("Play analysis region", html)
            self.assertIn("Use selected as start", html)
            self.assertIn("Silence Score Slice", html)


if __name__ == "__main__":
    unittest.main()
