from __future__ import annotations

import unittest

from quran_aligner.cli import _parse_time_value, build_parser


class CliTimeParsingTests(unittest.TestCase):
    def test_parse_time_value_accepts_milliseconds(self) -> None:
        self.assertEqual(_parse_time_value("569120"), 569120)

    def test_parse_time_value_accepts_minute_second_hundredths(self) -> None:
        self.assertEqual(_parse_time_value("09:34.40"), 574400)
        self.assertEqual(_parse_time_value("09:45.52"), 585520)

    def test_parser_accepts_timestamp_region_flags(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "align",
                "example.mp3",
                "13",
                "--inspect-only",
                "--inspect-region-start-ms",
                "09:34.40",
                "--inspect-region-end-ms",
                "09:45.52",
            ]
        )
        self.assertEqual(args.inspect_region_start_ms, 574400)
        self.assertEqual(args.inspect_region_end_ms, 585520)

    def test_parser_accepts_alignment_model_and_quran_profile(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "align",
                "example.mp3",
                "13",
                "--alignment-model",
                "rabah2026/wav2vec2-large-xlsr-53-arabic-quran-v_final",
                "--normalization-profile",
                "quran_uthmani",
            ]
        )
        self.assertEqual(args.alignment_model, "rabah2026/wav2vec2-large-xlsr-53-arabic-quran-v_final")
        self.assertEqual(args.normalization_profile, "quran_uthmani")


if __name__ == "__main__":
    unittest.main()
