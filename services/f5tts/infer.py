from __future__ import annotations

import json
from pathlib import Path

from f5_tts.api import F5TTS


def generate_from_payload(payload_path: str) -> None:
    payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
    out = Path(payload["output_path"])
    out.parent.mkdir(parents=True, exist_ok=True)

    tts = F5TTS()
    tts.infer(
        ref_file=payload["voice_path"],
        ref_text="",
        gen_text=payload["text"],
        file_wave=str(out),
    )
