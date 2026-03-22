from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from services.f5tts.engine import SpeechRequest, TTSService


ROOT_DIR = Path(__file__).resolve().parents[2]
VOICES_DIR = ROOT_DIR / "voices"
GENERATED_DIR = ROOT_DIR / "generated"
CONFIG_PATH = ROOT_DIR / "config" / "default.json"

app = FastAPI(title="local-tts-service", version="0.1.0")


def _load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _voice_metadata_path(voice_id: str) -> Path:
    return VOICES_DIR / voice_id / "metadata.json"


def _voice_sample_path(voice_id: str) -> Path:
    return VOICES_DIR / voice_id / "sample.wav"


def _read_voice_metadata(voice_id: str) -> dict[str, Any]:
    metadata_path = _voice_metadata_path(voice_id)
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail=f"Voice '{voice_id}' does not exist")
    with metadata_path.open("r", encoding="utf-8") as handle:
        metadata = json.load(handle)
    metadata["id"] = voice_id
    return metadata


def _ensure_dirs() -> None:
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)


@app.on_event("startup")
def on_startup() -> None:
    _ensure_dirs()


class TTSRequest(BaseModel):
    text: str = Field(min_length=1)
    voice: str = Field(min_length=1)
    format: str = Field(default="wav")
    style: dict[str, Any] | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/voices")
def list_voices() -> dict[str, list[dict[str, Any]]]:
    _ensure_dirs()
    voices: list[dict[str, Any]] = []
    for path in sorted(VOICES_DIR.iterdir()):
        if not path.is_dir():
            continue
        metadata_path = path / "metadata.json"
        if not metadata_path.exists():
            continue
        with metadata_path.open("r", encoding="utf-8") as handle:
            metadata = json.load(handle)
        metadata["id"] = path.name
        metadata["has_sample"] = (path / "sample.wav").exists()
        voices.append(metadata)
    return {"voices": voices}


@app.post("/voices")
async def create_voice(
    reference_audio: UploadFile = File(...),
    name: str = Form("Custom Voice"),
    description: str = Form(""),
    source: str = Form("recorded"),
    transcript: str | None = Form(None),
) -> dict[str, Any]:
    _ensure_dirs()
    safe_name = "_".join(name.lower().split()) or "voice"
    voice_id = f"{safe_name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
    voice_dir = VOICES_DIR / voice_id
    voice_dir.mkdir(parents=True, exist_ok=False)

    sample_path = voice_dir / "sample.wav"
    with sample_path.open("wb") as handle:
        shutil.copyfileobj(reference_audio.file, handle)

    metadata = {
        "name": name,
        "description": description,
        "source": source,
        "transcript": transcript,
        "created_at": datetime.utcnow().date().isoformat(),
    }
    with (voice_dir / "metadata.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)

    return {"voice_id": voice_id, "metadata": metadata}


@app.post("/voices/create")
async def create_voice_alias(
    reference_audio: UploadFile = File(...),
    name: str = Form("Custom Voice"),
    description: str = Form(""),
    source: str = Form("recorded"),
    transcript: str | None = Form(None),
) -> dict[str, Any]:
    return await create_voice(reference_audio, name, description, source, transcript)


@app.delete("/voices/{voice_id}")
def delete_voice(voice_id: str) -> dict[str, str]:
    voice_dir = VOICES_DIR / voice_id
    if not voice_dir.exists() or not voice_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Voice '{voice_id}' does not exist")
    shutil.rmtree(voice_dir)
    return {"deleted": voice_id}


@app.post("/tts")
def generate_tts(request: TTSRequest) -> FileResponse:
    if request.format.lower() != "wav":
        raise HTTPException(status_code=400, detail="Only wav format is currently supported")
    voice_sample = _voice_sample_path(request.voice)
    if not voice_sample.exists():
        raise HTTPException(status_code=404, detail=f"Voice '{request.voice}' not found")

    output_filename = f"{request.voice}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}.wav"
    output_path = GENERATED_DIR / output_filename

    config = _load_config()
    tts = TTSService(config=config)
    tts.generate_speech(
        SpeechRequest(
            text=request.text,
            voice_path=voice_sample,
            output_path=output_path,
            style=request.style,
        )
    )

    headers = {"X-Audio-Path": str(output_path.relative_to(ROOT_DIR))}
    return FileResponse(path=output_path, media_type="audio/wav", filename=output_filename, headers=headers)


@app.post("/tts/stream")
def stream_tts(request: TTSRequest) -> StreamingResponse:
    if request.format.lower() != "wav":
        raise HTTPException(status_code=400, detail="Only wav format is currently supported")
    voice_sample = _voice_sample_path(request.voice)
    if not voice_sample.exists():
        raise HTTPException(status_code=404, detail=f"Voice '{request.voice}' not found")

    output_filename = f"{request.voice}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}.wav"
    output_path = GENERATED_DIR / output_filename

    config = _load_config()
    tts = TTSService(config=config)
    tts.generate_speech(
        SpeechRequest(
            text=request.text,
            voice_path=voice_sample,
            output_path=output_path,
            style=request.style,
        )
    )

    def iter_chunks() -> Any:
        with output_path.open("rb") as handle:
            while True:
                chunk = handle.read(4096)
                if not chunk:
                    break
                yield chunk

    headers = {"X-Audio-Path": str(output_path.relative_to(ROOT_DIR))}
    return StreamingResponse(iter_chunks(), media_type="audio/wav", headers=headers)
