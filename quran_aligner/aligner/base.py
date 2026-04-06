from __future__ import annotations

from typing import Protocol

from ..models import AlignmentResult, TokenRef


class AlignmentBackend(Protocol):
    def align(self, audio_path: str, tokens: list[TokenRef]) -> AlignmentResult:
        ...


def make_backend(
    name: str,
    *,
    state_dp_engine: str = "native",
    state_dp_mode: str = "jump",
    alignment_model: str | None = None,
) -> AlignmentBackend:
    normalized = name.lower()
    if normalized == "ctc":
        from .ctc_forced_backend import CTCForcedAlignerBackend

        kwargs = {
            "state_dp_engine": state_dp_engine,
            "state_dp_mode": state_dp_mode,
        }
        if alignment_model is not None:
            kwargs["alignment_model"] = alignment_model
        return CTCForcedAlignerBackend(**kwargs)
    if normalized == "baseline":
        from .baseline_backend import BaselineBackend

        return BaselineBackend()
    raise ValueError(f"Unsupported backend: {name}")
