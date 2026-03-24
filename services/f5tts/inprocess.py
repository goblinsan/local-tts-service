from __future__ import annotations

import os
import shutil
import threading
from pathlib import Path

import pydub.utils as pydub_utils
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
        preferred_entries.append(str(Path(ffmpeg_path).resolve().parent))
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
        pydub_utils.get_encoder_name = lambda: resolved_ffmpeg
    if resolved_ffprobe:
        AudioSegment.ffprobe = resolved_ffprobe
        pydub_utils.get_prober_name = lambda: resolved_ffprobe


class InProcessF5Engine:
    def __init__(self) -> None:
        self._model = None
        self._init_lock = threading.Lock()
        self._infer_lock = threading.Lock()

    def _get_model(self):
        if self._model is not None:
            return self._model

        with self._init_lock:
            if self._model is not None:
                return self._model

            _configure_ffmpeg_paths()
            from f5_tts.api import F5TTS

            self._model = F5TTS()
            return self._model

    def generate(
        self,
        text: str,
        voice_path: str,
        output_path: str,
        reference_text: str,
        speed: float = 0.95,
        nfe_step: int = 32,
        cfg_strength: float = 2.0,
        fix_duration: float | None = None,
    ) -> None:
        model = self._get_model()
        with self._infer_lock:
            model.infer(
                ref_file=voice_path,
                ref_text=reference_text,
                gen_text=text,
                speed=speed,
                nfe_step=nfe_step,
                cfg_strength=cfg_strength,
                fix_duration=fix_duration,
                remove_silence=False,
                file_wave=output_path,
            )


ENGINE = InProcessF5Engine()
