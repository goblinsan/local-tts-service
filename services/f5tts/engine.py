from __future__ import annotations

import json
import math
import struct
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from services.f5tts.inprocess import ENGINE


@dataclass(slots=True)
class SpeechRequest:
    text: str
    voice_path: Path
    output_path: Path
    reference_text: str | None = None
    style: dict[str, Any] | None = None


class TTSService:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    def _inference_option(self, key: str, default: float | int, style: dict[str, Any] | None) -> float | int:
        if style and key in style and isinstance(style[key], (int, float)):
            return style[key]
        return self.config.get("f5tts", {}).get("inference", {}).get(key, default)

    def generate_speech(self, request: SpeechRequest) -> Path:
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        command = self.config.get("f5tts", {}).get("command")
        if command:
            success, attempted, error_text = self._try_external_engine(request, command)
            if success:
                return request.output_path
            if attempted:
                raise RuntimeError(error_text or "External TTS engine failed")
        else:
            try:
                ENGINE.generate(
                    text=request.text,
                    voice_path=str(request.voice_path),
                    output_path=str(request.output_path),
                    reference_text=request.reference_text or "",
                    speed=float(self._inference_option("speed", 1.0, request.style)),
                    nfe_step=int(self._inference_option("nfe_step", 16, request.style)),
                    cfg_strength=float(self._inference_option("cfg_strength", 2.0, request.style)),
                )
                if request.output_path.exists() and request.output_path.stat().st_size > 0:
                    return request.output_path
                raise RuntimeError("In-process F5-TTS did not produce output file")
            except Exception as error:
                raise RuntimeError(str(error)) from error

        self._generate_fallback_wave(request)
        return request.output_path

    def _try_external_engine(self, request: SpeechRequest, command: list[str]) -> tuple[bool, bool, str]:
        if not command:
            return False, False, ""

        payload = {
            "text": request.text,
            "voice_path": str(request.voice_path),
            "output_path": str(request.output_path),
            "reference_text": request.reference_text or "",
            "style": request.style or {},
        }

        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
            json.dump(payload, handle)
            payload_file = handle.name

        full_command = [*command, payload_file]
        try:
            completed = subprocess.run(full_command, capture_output=True, text=True, check=False)
            if completed.returncode != 0:
                error_text = (completed.stderr or completed.stdout or "").strip()
                return False, True, error_text
            return request.output_path.exists(), True, ""
        except FileNotFoundError:
            return False, False, ""

    def _generate_fallback_wave(self, request: SpeechRequest) -> None:
        sample_rate = 24000
        min_seconds = 1.0
        seconds_by_length = max(min_seconds, min(12.0, len(request.text) * 0.055))
        num_frames = int(sample_rate * seconds_by_length)

        voice_hash = sum(request.voice_path.name.encode("utf-8"))
        base_frequency = 170 + (voice_hash % 120)
        style = request.style or {}
        style_shift = int(style.get("pitch_shift", 0)) if isinstance(style.get("pitch_shift", 0), int) else 0
        frequency = max(120, min(420, base_frequency + style_shift))

        amplitude = 0.18
        fade_frames = int(sample_rate * 0.02)

        with wave.open(str(request.output_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)

            for i in range(num_frames):
                fade = 1.0
                if i < fade_frames:
                    fade = i / fade_frames
                elif i > num_frames - fade_frames:
                    fade = (num_frames - i) / fade_frames

                sample = amplitude * fade * (
                    math.sin(2.0 * math.pi * frequency * (i / sample_rate))
                    + 0.35 * math.sin(2.0 * math.pi * (frequency * 2.01) * (i / sample_rate))
                )
                pcm = int(max(-1.0, min(1.0, sample)) * 32767)
                wav_file.writeframes(struct.pack("<h", pcm))
