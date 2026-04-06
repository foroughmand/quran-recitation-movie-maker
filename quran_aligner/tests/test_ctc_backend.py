from __future__ import annotations

import unittest

from quran_aligner.aligner.ctc_forced_backend import CTCForcedAlignerBackend
from quran_aligner.models import TokenRef


class _FakeTokenizer:
    unk_token = "[UNK]"

    def get_vocab(self) -> dict[str, int]:
        return {
            "[UNK]": 99,
            "ا": 1,
            "ح": 2,
            "ِ": 3,
        }

    def convert_tokens_to_ids(self, token: str) -> int:
        mapping = {
            "[UNK]": 99,
            "ا": 1,
            "ح": 2,
            "ِ": 3,
        }
        return mapping.get(token, 99)


class CTCBackendTests(unittest.TestCase):
    def test_resolve_token_id_falls_back_for_unsupported_mark(self) -> None:
        backend = CTCForcedAlignerBackend()
        tokenizer = _FakeTokenizer()
        dictionary = {
            "ا": 1,
            "[unk]": 99,
        }

        self.assertEqual(backend._resolve_token_id(tokenizer, dictionary, "ٰ"), 99)
        self.assertEqual(backend._resolve_token_id(tokenizer, dictionary, "ا"), 1)

    def test_prepare_tokens_filters_unsupported_chars_per_model(self) -> None:
        backend = CTCForcedAlignerBackend(alignment_model="example/model")
        backend._ensure_model = lambda: None
        backend._tokenizer = _FakeTokenizer()
        tokens = [
            TokenRef(
                ayah_number=1,
                word_index_in_ayah=1,
                original_word="ٱ",
                normalized_word="ٱ",
                normalization_profile="quran_uthmani",
            )
        ]

        prepared = backend.prepare_tokens(tokens)

        self.assertEqual([token.normalized_word for token in prepared], ["ا"])

    def test_emissions_cache_key_includes_model_identity(self) -> None:
        backend = CTCForcedAlignerBackend(alignment_model="model-a")
        self.assertIn("::model-a", backend._build_emissions_cache_key("sample.wav"))

    def test_resolve_unit_token_ids_expands_grapheme_into_model_symbols(self) -> None:
        backend = CTCForcedAlignerBackend()
        tokenizer = _FakeTokenizer()
        dictionary = {key.lower(): value for key, value in tokenizer.get_vocab().items()}

        self.assertEqual(backend._resolve_unit_token_ids(tokenizer, dictionary, "حِ"), [2, 3])


if __name__ == "__main__":
    unittest.main()
