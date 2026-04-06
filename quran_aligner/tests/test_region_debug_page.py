from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from quran_aligner.region_debug_page import write_region_debug_data_js, write_region_debug_html


class RegionDebugPageTests(unittest.TestCase):
    def test_writes_interactive_region_inspector(self) -> None:
        payload = {
            "region": {
                "start_ms": 1000,
                "end_ms": 1600,
                "ayah_number": 23,
            },
            "audio": {
                "relative_path": "audio.mp3",
                "duration_ms": 12000,
                "duration_label": "00:12.000",
            },
            "tokens": [
                {
                    "index": 0,
                    "ayah_number": 23,
                    "word_index_in_ayah": 4,
                    "original_word": "قال",
                    "normalized_word": "قال",
                }
            ],
            "runs": [
                {
                    "run_index": 0,
                    "global_word_index": 0,
                    "word": "قال",
                    "start_ms": 1000,
                    "end_ms": 1200,
                    "score": 0.7,
                    "frame_count": 2,
                }
            ],
            "decoder": {
                "bucket_count": 3,
                "bucket_ms": 200,
                "state_count": 2,
                "state_rows": [
                    {
                        "state_index": 0,
                        "global_word_index": 0,
                        "ayah_number": 23,
                        "char": "ق",
                        "word": "قال",
                        "normalized_word": "قال",
                        "word_index_in_ayah": 4,
                        "label": "0: ق (w1 قال)",
                    },
                    {
                        "state_index": 1,
                        "global_word_index": 0,
                        "ayah_number": 23,
                        "char": "ا",
                        "word": "قال",
                        "normalized_word": "قال",
                        "word_index_in_ayah": 4,
                        "label": "1: ا (w1 قال)",
                    },
                ],
                "scoring_matrix": [[0.1, 0.4, 0.2], [0.2, 0.5, 0.3]],
                "dp_scores": [[None, 0.1, 0.5, 0.7], [None, None, 0.6, 1.0]],
                "backpointers": [
                    [None, {"prev_state_index": None, "prev_bucket": 0}, {"prev_state_index": 0, "prev_bucket": 1}, {"prev_state_index": 0, "prev_bucket": 2}],
                    [None, None, {"prev_state_index": 0, "prev_bucket": 1}, {"prev_state_index": 1, "prev_bucket": 2}],
                ],
                "bucket_to_state": [0, 1, 1],
                "bucket_to_word": [0, 0, 0],
                "phrase_trace": [
                    {
                        "previous_state_index": None,
                        "start_word_index": 0,
                        "end_word_index": 0,
                        "start_bucket": 0,
                        "end_bucket": 1,
                        "repair_width": 1,
                    }
                ],
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = Path(tmpdir) / "region-inspect.html"
            js_path = Path(tmpdir) / "region-inspect.data.js"
            write_region_debug_html(html_path, payload)
            write_region_debug_data_js(js_path, payload)
            html = html_path.read_text(encoding="utf-8")
            js = js_path.read_text(encoding="utf-8")
            self.assertIn("Audio Sync", html)
            self.assertIn("state-chip", html)
            self.assertIn("selection-summary", html)
            self.assertIn("Selection start", html)
            self.assertIn("Selection end", html)
            self.assertIn("Play selected time range", html)
            self.assertIn("Shift-click a second bucket", html)
            self.assertIn("Drag across columns", html)
            self.assertIn("Play current bucket", html)
            self.assertIn("Scoring Matrix", html)
            self.assertIn("DP Matrix", html)
            self.assertIn("Silence Scores", html)
            self.assertIn("region-inspect.data.js", html)
            self.assertIn("state_rows", js)
            self.assertIn("raw_bucket_to_state", js)


if __name__ == "__main__":
    unittest.main()
