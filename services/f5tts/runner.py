from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pydub.utils as pydub_utils
from pydub.exceptions import CouldntDecodeError
from pydub import AudioSegment


def _configure_ffmpeg_paths() -> None:
    link_entries: list[str] = []
    preferred_entries: list[str] = []

    winget_links = Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links"
    if winget_links.exists():
        link_entries.append(str(winget_links))

    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")

    if ffmpeg_path:
        ffmpeg_parent = str(Path(ffmpeg_path).resolve().parent)
        preferred_entries.append(ffmpeg_parent)
    if ffprobe_path:
        ffprobe_parent = str(Path(ffprobe_path).resolve().parent)
        if ffprobe_parent not in preferred_entries:
            preferred_entries.append(ffprobe_parent)

    for entry in link_entries:
        if entry not in preferred_entries:
            preferred_entries.append(entry)

    current_path = os.environ.get("PATH", "")
    existing_entries = [entry for entry in current_path.split(";") if entry]
    merged_entries = [entry for entry in preferred_entries if entry]
    merged_entries.extend(entry for entry in existing_entries if entry not in merged_entries)
    os.environ["PATH"] = ";".join(merged_entries)

    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")

    resolved_ffmpeg = str(Path(ffmpeg_path).resolve()) if ffmpeg_path else None
    resolved_ffprobe = str(Path(ffprobe_path).resolve()) if ffprobe_path else None

    if resolved_ffmpeg:
        AudioSegment.converter = resolved_ffmpeg
        os.environ["FFMPEG_BINARY"] = resolved_ffmpeg
    if resolved_ffprobe:
        AudioSegment.ffprobe = resolved_ffprobe

    if resolved_ffmpeg:
        pydub_utils.get_encoder_name = lambda: resolved_ffmpeg
    if resolved_ffprobe:
        pydub_utils.get_prober_name = lambda: resolved_ffprobe


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m services.f5tts.runner <payload.json>", file=sys.stderr)
        return 2

    payload_path = Path(sys.argv[1])
    payload = json.loads(payload_path.read_text(encoding="utf-8"))

    text = payload["text"]
    ref_audio = payload["voice_path"]
    output_path = Path(payload["output_path"])
    reference_text = (payload.get("reference_text") or "").strip()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    _configure_ffmpeg_paths()

    from f5_tts.api import F5TTS

    try:
        tts = F5TTS()
        tts.infer(
            ref_file=ref_audio,
            ref_text=reference_text,
            gen_text=text,
            file_wave=str(output_path),
        )
    except CouldntDecodeError as error:
        print(f"Could not decode reference audio '{ref_audio}'. Ensure it is a valid WAV/MP3 file: {error}", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"F5-TTS inference failed: {error}", file=sys.stderr)
        return 1

    if not output_path.exists() or output_path.stat().st_size == 0:
        print("F5-TTS did not produce output file", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
