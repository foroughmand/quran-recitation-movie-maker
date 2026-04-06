from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


BITRATES = {
    ("1", "1"): [0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448, 0],
    ("1", "2"): [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384, 0],
    ("1", "3"): [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0],
    ("2", "1"): [0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256, 0],
    ("2", "2"): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0],
    ("2", "3"): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0],
}

SAMPLE_RATES = {
    "1": [44100, 48000, 32000, 0],
    "2": [22050, 24000, 16000, 0],
    "2.5": [11025, 12000, 8000, 0],
}


@dataclass(slots=True)
class Mp3Info:
    duration_seconds: float
    frame_count: int
    sample_count: int
    sample_rate: int


def _skip_id3(data: bytes) -> int:
    if len(data) >= 10 and data[:3] == b"ID3":
        size_bytes = data[6:10]
        size = 0
        for byte in size_bytes:
            size = (size << 7) | (byte & 0x7F)
        return 10 + size
    return 0


def _parse_header(header: int) -> tuple[int, int, int] | None:
    if (header >> 21) & 0x7FF != 0x7FF:
        return None

    version_bits = (header >> 19) & 0x3
    layer_bits = (header >> 17) & 0x3
    bitrate_idx = (header >> 12) & 0xF
    sample_rate_idx = (header >> 10) & 0x3
    padding = (header >> 9) & 0x1

    if version_bits == 1 or layer_bits == 0 or bitrate_idx in (0, 15) or sample_rate_idx == 3:
        return None

    version = {0: "2.5", 2: "2", 3: "1"}[version_bits]
    layer = {1: "3", 2: "2", 3: "1"}[layer_bits]
    family = "1" if version == "1" else "2"
    bitrate_kbps = BITRATES[(family, layer)][bitrate_idx]
    sample_rate = SAMPLE_RATES[version][sample_rate_idx]
    if bitrate_kbps <= 0 or sample_rate <= 0:
        return None

    if layer == "1":
        frame_length = ((12 * bitrate_kbps * 1000) // sample_rate + padding) * 4
        samples_per_frame = 384
    else:
        samples_per_frame = 1152 if version == "1" or layer != "3" else 576
        coef = 144 if layer != "3" or version == "1" else 72
        frame_length = (coef * bitrate_kbps * 1000) // sample_rate + padding

    if frame_length <= 0:
        return None
    return frame_length, samples_per_frame, sample_rate


def read_mp3_info(path: str | Path) -> Mp3Info:
    data = Path(path).read_bytes()
    pos = _skip_id3(data)
    sample_count = 0
    frame_count = 0
    sample_rate = 0

    while pos + 4 <= len(data):
        header = int.from_bytes(data[pos : pos + 4], "big")
        parsed = _parse_header(header)
        if parsed is None:
            pos += 1
            continue
        frame_length, samples_per_frame, sample_rate = parsed
        if pos + frame_length > len(data):
            break
        sample_count += samples_per_frame
        frame_count += 1
        pos += frame_length

    if frame_count == 0 or sample_rate == 0:
        raise RuntimeError(f"Could not parse MP3 frames from {path}")

    return Mp3Info(
        duration_seconds=sample_count / sample_rate,
        frame_count=frame_count,
        sample_count=sample_count,
        sample_rate=sample_rate,
    )
