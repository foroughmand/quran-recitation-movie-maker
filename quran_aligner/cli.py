from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import os

from .app import inspect_alignment_region, inspect_alignment_region_only, run_alignment
from .aligner.base import make_backend
from .normalizer import DEFAULT_CTC_ALIGNMENT_MODEL
from .progress import ProgressReporter


def _parse_time_value(value: str) -> int:
    text = value.strip()
    if not text:
        raise argparse.ArgumentTypeError("Time value cannot be empty.")
    if text.isdigit():
        return int(text)

    parts = text.split(":")
    if len(parts) == 2:
        minutes_text, seconds_text = parts
        try:
            minutes = int(minutes_text)
            seconds = float(seconds_text)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                f"Invalid time value '{value}'. Use milliseconds or MM:SS.xx."
            ) from exc
        if minutes < 0 or seconds < 0 or seconds >= 60:
            raise argparse.ArgumentTypeError(
                f"Invalid time value '{value}'. Seconds must be between 0 and 59.999."
            )
        return int(round((minutes * 60 + seconds) * 1000))

    raise argparse.ArgumentTypeError(
        f"Invalid time value '{value}'. Use milliseconds or MM:SS.xx."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Align a Qur'an recitation audio file to ayah timings.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    align = subparsers.add_parser("align", help="Generate alignment outputs for one surah/audio pair.")
    align.add_argument("audio_path", help="Path to the recitation audio file.")
    align.add_argument("surah_number", type=int, help="Surah number from 1 to 114.")
    align.add_argument("--mode", choices=("full", "ayah", "test"), default="full")
    align.add_argument("--ayah-number", type=int, help="Ayah number to align when --mode ayah is used.")
    align.add_argument("--include-bismillah-mode", choices=("auto", "force", "off"), default="auto")
    align.add_argument("--backend", choices=("auto", "ctc", "baseline"), default="auto")
    align.add_argument("--alignment-model", default=None, help=f"Hugging Face model name/path for the CTC backend. Defaults to {DEFAULT_CTC_ALIGNMENT_MODEL}.")
    align.add_argument("--state-dp-engine", choices=("native", "python"), default="native")
    align.add_argument("--state-dp-mode", choices=("jump", "step_by_step"), default="jump")
    align.add_argument("--normalization-profile", choices=("light", "moderate", "aggressive", "quran_uthmani"), default=None)
    align.add_argument("--min-word-score", type=float, default=0.45)
    align.add_argument("--local-window-ms", type=int, default=250)
    align.add_argument("--local-phrase-words", type=int, default=3)
    align.add_argument("--max-gap-to-absorb-ms", type=int, default=120)
    align.add_argument("--show-suspicious-only", action="store_true")
    align.add_argument("--disable-refinement", action="store_true")
    align.add_argument("--enable-refinement", action="store_true")
    align.add_argument("--output-dir", default="alignment_out")
    align.add_argument("--output-path")
    align.add_argument("--debug-path")
    align.add_argument("--review-path")
    align.add_argument(
        "--inspect-region-start-ms",
        type=_parse_time_value,
        help="Run a focused decoder inspection on this audio region start. Accepts milliseconds or MM:SS.xx.",
    )
    align.add_argument(
        "--inspect-region-end-ms",
        type=_parse_time_value,
        help="Run a focused decoder inspection on this audio region end. Accepts milliseconds or MM:SS.xx.",
    )
    align.add_argument("--inspect-ayah-number", type=int, help="Limit region inspection to one ayah's transcript words.")
    align.add_argument("--inspect-word-start", type=int, help="1-based start word in ayah for region inspection.")
    align.add_argument("--inspect-word-end", type=int, help="1-based end word in ayah for region inspection.")
    align.add_argument("--inspect-only", action="store_true", help="Only run the focused region decoder inspection.")
    align.add_argument(
        "--prefer-local-text",
        action="store_true",
        help="Skip Quran.com and use local data/quran-simple-plain-*.txt files immediately.",
    )
    align.set_defaults(func=_run_align)

    serve = subparsers.add_parser("serve", help="Serve an output directory locally for browser review.")
    serve.add_argument("--directory", default="alignment_out")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.set_defaults(func=_run_serve)
    return parser


def _run_align(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "run.log"

    with ProgressReporter(log_path=log_path) as reporter:
        reporter.log(
            f"Starting alignment: audio={Path(args.audio_path).resolve()} surah={args.surah_number} "
            f"backend={args.backend} mode={args.mode}"
        )
        if args.inspect_only:
            if args.inspect_region_start_ms is None or args.inspect_region_end_ms is None:
                raise ValueError("--inspect-only requires --inspect-region-start-ms and --inspect-region-end-ms")
            reporter.log("Running region-only inspection; full-surah alignment is skipped.")
            inspect_alignment_region_only(
                audio_path=args.audio_path,
                surah_number=args.surah_number,
                backend=make_backend(
                    args.backend if args.backend != "auto" else "ctc",
                    state_dp_engine=args.state_dp_engine,
                    state_dp_mode=args.state_dp_mode,
                    alignment_model=args.alignment_model,
                ),
                output_dir=output_dir,
                start_ms=args.inspect_region_start_ms,
                end_ms=args.inspect_region_end_ms,
                alignment_model=args.alignment_model,
                normalization_profile=args.normalization_profile,
                prefer_remote_text=not args.prefer_local_text,
                ayah_number=args.inspect_ayah_number,
                word_start=args.inspect_word_start,
                word_end=args.inspect_word_end,
                progress_callback=reporter.event,
            )
            reporter.log(f"Region inspection HTML: {output_dir / 'region-inspect.html'}")
            reporter.log(f"Region inspection JSON: {output_dir / 'region-inspect.debug.json'}")
            reporter.log(f"Run log: {log_path}")
            return
        run = run_alignment(
            args.audio_path,
            args.surah_number,
            mode=args.mode,
            ayah_number=args.ayah_number,
            include_bismillah_mode=args.include_bismillah_mode,
            backend_name=args.backend,
            alignment_model=args.alignment_model,
            state_dp_engine=args.state_dp_engine,
            state_dp_mode=args.state_dp_mode,
            normalization_profile=args.normalization_profile,
            min_word_score=args.min_word_score,
            local_window_ms=args.local_window_ms,
            local_phrase_words=args.local_phrase_words,
            max_gap_to_absorb_ms=args.max_gap_to_absorb_ms,
            disable_refinement=(not args.enable_refinement) or args.disable_refinement,
            show_suspicious_only=args.show_suspicious_only,
            output_dir=str(output_dir),
            output_path=args.output_path,
            debug_path=args.debug_path,
            review_path=args.review_path,
            prefer_remote_text=not args.prefer_local_text,
            progress_callback=reporter.event,
        )
        reporter.log(
            f"Aligned surah {run.surah.surah_number} in mode={args.mode} with backend={run.result.backend}; "
            f"produced {len(run.ayah_alignments)} ayah spans."
        )
        if run.refinement is not None:
            reporter.log(
                f"Refinement tried {len(run.refinement.region_logs)} region(s); "
                f"changed {run.refinement.changed_word_count} word(s); "
                f"total boundary shift {run.refinement.total_boundary_shift_ms} ms."
            )
            for note in run.refinement.notes[:5]:
                reporter.log(f"  - {note}")
        if args.inspect_region_start_ms is not None and args.inspect_region_end_ms is not None:
            reporter.log(
                f"Inspecting decoder region {args.inspect_region_start_ms}-{args.inspect_region_end_ms} ms"
            )
            inspect_alignment_region(
                run=run,
                audio_path=args.audio_path,
                backend=make_backend(
                    args.backend if args.backend != "auto" else run.result.backend,
                    state_dp_engine=args.state_dp_engine,
                    state_dp_mode=args.state_dp_mode,
                    alignment_model=args.alignment_model or run.result.metadata.get("alignment_model"),
                ),
                output_dir=output_dir,
                start_ms=args.inspect_region_start_ms,
                end_ms=args.inspect_region_end_ms,
                ayah_number=args.inspect_ayah_number,
                word_start=args.inspect_word_start,
                word_end=args.inspect_word_end,
                progress_callback=reporter.event,
            )
            reporter.log(f"Region inspection HTML: {output_dir / 'region-inspect.html'}")
            reporter.log(f"Region inspection JSON: {output_dir / 'region-inspect.debug.json'}")
        reporter.log(f"Results written to {output_dir}")
        reporter.log(f"Review HTML: {output_dir / 'index.html'}")
        reporter.log(f"Run log: {log_path}")


def _run_serve(args: argparse.Namespace) -> None:
    root = Path(args.directory).resolve()
    os.chdir(root)
    server = ThreadingHTTPServer((args.host, args.port), SimpleHTTPRequestHandler)
    print(f"Serving {root} at http://{args.host}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
