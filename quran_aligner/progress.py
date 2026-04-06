from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys
from typing import TextIO

from tqdm.auto import tqdm


@dataclass(slots=True)
class ProgressEvent:
    stage: str
    message: str
    completed: int | None = None
    total: int | None = None


class ProgressReporter:
    def __init__(self, *, log_path: str | Path | None = None, stream: TextIO | None = None) -> None:
        self.stream = stream or sys.stdout
        self.log_path = Path(log_path).resolve() if log_path is not None else None
        self._log_handle: TextIO | None = None
        self._bar = None
        self._bar_stage: str | None = None
        self._bar_total: int | None = None
        self._bar_completed = 0

    def __enter__(self) -> "ProgressReporter":
        if self.log_path is not None:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_handle = self.log_path.open("w", encoding="utf-8")
            self.log(f"Writing run log to {self.log_path}")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._close_bar()
        if self._log_handle is not None:
            self._log_handle.close()
            self._log_handle = None

    def log(self, message: str) -> None:
        timestamped = f"[{self._timestamp()}] {message}"
        tqdm.write(timestamped, file=self.stream)
        if self._log_handle is not None:
            print(timestamped, file=self._log_handle, flush=True)

    def progress(self, stage: str, message: str, completed: int | None = None, total: int | None = None) -> None:
        if completed is None or total is None or total <= 0:
            self._close_bar()
            self.log(f"[{stage}] {message}")
            return
        if self._bar is None or self._bar_stage != stage or self._bar_total != total:
            self._close_bar()
            self._bar = tqdm(
                total=total,
                desc=stage,
                file=self.stream,
                leave=False,
                dynamic_ncols=True,
            )
            self._bar_stage = stage
            self._bar_total = total
            self._bar_completed = 0
        delta = max(0, completed - self._bar_completed)
        if delta:
            self._bar.update(delta)
            self._bar_completed = completed
        self._bar.set_postfix_str(message)
        if self._log_handle is not None:
            print(
                f"[{self._timestamp()}] [{stage}] ({completed}/{total}) {message}",
                file=self._log_handle,
                flush=True,
            )

    def event(self, event: ProgressEvent) -> None:
        self.progress(
            stage=event.stage,
            message=event.message,
            completed=event.completed,
            total=event.total,
        )

    def _close_bar(self) -> None:
        if self._bar is not None:
            self._bar.close()
            self._bar = None
            self._bar_stage = None
            self._bar_total = None
            self._bar_completed = 0

    @staticmethod
    def _timestamp() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
