from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from services.f5tts.engine import SpeechRequest, TTSService


ROOT_DIR = Path(__file__).resolve().parents[2]
VOICES_DIR = ROOT_DIR / "voices"
GENERATED_DIR = ROOT_DIR / "generated"
CONFIG_PATH = ROOT_DIR / "config" / "default.json"
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="local-tts-service", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _voice_metadata_path(voice_id: str) -> Path:
    return VOICES_DIR / voice_id / "metadata.json"


def _voice_sample_path(voice_id: str) -> Path:
    return VOICES_DIR / voice_id / "sample.wav"


def _resolve_ffmpeg_binary() -> str:
    winget_links = Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links"
    path_env = os.environ.get("PATH", "")
    if winget_links.exists() and str(winget_links) not in path_env:
        os.environ["PATH"] = f"{winget_links};{path_env}" if path_env else str(winget_links)

    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return str(Path(ffmpeg_path).resolve())

    package_root = Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages"
    matches = sorted(package_root.glob("Gyan.FFmpeg.Shared_*/*/bin/ffmpeg.exe"))
    if matches:
        return str(matches[-1])

    raise HTTPException(
        status_code=500,
        detail="FFmpeg is not available. Install a shared FFmpeg build and retry voice creation.",
    )


def _normalize_reference_audio(upload: UploadFile, output_path: Path) -> None:
    file_suffix = Path(upload.filename or "").suffix or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix) as temp_file:
        temp_input_path = Path(temp_file.name)
        shutil.copyfileobj(upload.file, temp_file)

    ffmpeg_exe = _resolve_ffmpeg_binary()
    ffmpeg_dir = str(Path(ffmpeg_exe).parent)

    env = os.environ.copy()
    env_path = env.get("PATH", "")
    if ffmpeg_dir not in env_path:
        env["PATH"] = f"{ffmpeg_dir};{env_path}" if env_path else ffmpeg_dir

    ffmpeg_cmd = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(temp_input_path),
        "-ac",
        "1",
        "-ar",
        "24000",
        "-vn",
        str(output_path),
    ]

    try:
        completed = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, check=False, env=env)
        if completed.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:
            error_text = (completed.stderr or completed.stdout or "").strip()
            raise HTTPException(status_code=400, detail=f"Invalid reference audio: {error_text[:500]}")
    finally:
        temp_input_path.unlink(missing_ok=True)


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


def _delete_generated_files() -> dict[str, Any]:
    deleted_files = 0
    skipped_entries = 0
    bytes_freed = 0
    failed_files: list[dict[str, str]] = []

    for entry in GENERATED_DIR.iterdir():
        if not entry.is_file() and not entry.is_symlink():
            skipped_entries += 1
            continue

        try:
            file_size = entry.stat().st_size
        except OSError:
            file_size = 0

        try:
            entry.unlink(missing_ok=True)
            deleted_files += 1
            bytes_freed += file_size
        except OSError as error:
            failed_files.append({"name": entry.name, "error": str(error)})

    return {
        "deleted_files": deleted_files,
        "skipped_entries": skipped_entries,
        "bytes_freed": bytes_freed,
        "failed_files": failed_files,
    }


def _prepare_reference_text(raw_text: str) -> str:
    text = " ".join(raw_text.split())
    words = text.split()
    if len(words) > 30:
        text = " ".join(words[:30])
    return text[:220]


@app.on_event("startup")
def on_startup() -> None:
    _ensure_dirs()


class TTSRequest(BaseModel):
    text: str = Field(min_length=1)
    voice: str = Field(min_length=1)
    format: str = Field(default="wav")
    style: dict[str, Any] | None = None


class VoiceUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    transcript: str | None = None


@app.get("/", response_class=RedirectResponse)
def root() -> RedirectResponse:
    return RedirectResponse(url="/static/index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/runtime")
def runtime_info() -> dict[str, Any]:
    try:
        import torch

        return {
            "torch_version": torch.__version__,
            "cuda_available": bool(torch.cuda.is_available()),
            "device": "cuda" if torch.cuda.is_available() else "cpu",
        }
    except Exception:
        return {
            "torch_version": "unknown",
            "cuda_available": False,
            "device": "cpu",
        }


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
        sample_path = path / "sample.wav"
        metadata["id"] = path.name
        metadata["has_sample"] = sample_path.exists() and sample_path.stat().st_size > 0
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
    _normalize_reference_audio(reference_audio, sample_path)

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


@app.patch("/voices/{voice_id}")
def update_voice(voice_id: str, request: VoiceUpdateRequest) -> dict[str, Any]:
    metadata = _read_voice_metadata(voice_id)
    metadata_path = _voice_metadata_path(voice_id)

    if request.name is not None:
        metadata["name"] = request.name
    if request.description is not None:
        metadata["description"] = request.description
    if request.transcript is not None:
        metadata["transcript"] = request.transcript

    persisted = {key: value for key, value in metadata.items() if key != "id"}
    with metadata_path.open("w", encoding="utf-8") as handle:
        json.dump(persisted, handle, indent=2)

    metadata["id"] = voice_id
    return {"voice": metadata}


@app.delete("/voices/{voice_id}")
def delete_voice(voice_id: str) -> dict[str, str]:
    voice_dir = VOICES_DIR / voice_id
    if not voice_dir.exists() or not voice_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Voice '{voice_id}' does not exist")
    shutil.rmtree(voice_dir)
    return {"deleted": voice_id}


@app.delete("/admin/generated/files")
def delete_generated_files() -> dict[str, Any]:
    _ensure_dirs()
    result = _delete_generated_files()
    result["directory"] = str(GENERATED_DIR.relative_to(ROOT_DIR))
    return result


@app.post("/tts")
def generate_tts(request: TTSRequest) -> FileResponse:
    if request.format.lower() != "wav":
        raise HTTPException(status_code=400, detail="Only wav format is currently supported")
    voice_sample = _voice_sample_path(request.voice)
    if not voice_sample.exists():
        raise HTTPException(status_code=404, detail=f"Voice '{request.voice}' not found")
    if voice_sample.stat().st_size == 0:
        raise HTTPException(
            status_code=400,
            detail=f"Voice '{request.voice}' has no valid sample.wav. Upload a real reference clip via POST /voices.",
        )
    voice_metadata = _read_voice_metadata(request.voice)
    transcript = (voice_metadata.get("transcript") or "").strip()
    if not transcript:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Voice '{request.voice}' is missing transcript metadata. "
                "Update the voice transcript so F5-TTS can use the reference clip reliably."
            ),
        )

    reference_text = _prepare_reference_text(transcript)

    output_filename = f"{request.voice}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}.wav"
    output_path = GENERATED_DIR / output_filename

    config = _load_config()
    tts = TTSService(config=config)
    try:
        tts.generate_speech(
            SpeechRequest(
                text=request.text,
                voice_path=voice_sample,
                output_path=output_path,
                reference_text=reference_text,
                style=request.style,
            )
        )
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=f"TTS engine error: {error}") from error

    headers = {"X-Audio-Path": str(output_path.relative_to(ROOT_DIR))}
    return FileResponse(path=output_path, media_type="audio/wav", filename=output_filename, headers=headers)


@app.post("/tts/stream")
def stream_tts(request: TTSRequest) -> StreamingResponse:
    if request.format.lower() != "wav":
        raise HTTPException(status_code=400, detail="Only wav format is currently supported")
    voice_sample = _voice_sample_path(request.voice)
    if not voice_sample.exists():
        raise HTTPException(status_code=404, detail=f"Voice '{request.voice}' not found")
    if voice_sample.stat().st_size == 0:
        raise HTTPException(
            status_code=400,
            detail=f"Voice '{request.voice}' has no valid sample.wav. Upload a real reference clip via POST /voices.",
        )
    voice_metadata = _read_voice_metadata(request.voice)
    transcript = (voice_metadata.get("transcript") or "").strip()
    if not transcript:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Voice '{request.voice}' is missing transcript metadata. "
                "Update the voice transcript so F5-TTS can use the reference clip reliably."
            ),
        )

    reference_text = _prepare_reference_text(transcript)

    output_filename = f"{request.voice}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}.wav"
    output_path = GENERATED_DIR / output_filename

    config = _load_config()
    tts = TTSService(config=config)
    try:
        tts.generate_speech(
            SpeechRequest(
                text=request.text,
                voice_path=voice_sample,
                output_path=output_path,
                reference_text=reference_text,
                style=request.style,
            )
        )
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=f"TTS engine error: {error}") from error

    def iter_chunks() -> Any:
        with output_path.open("rb") as handle:
            while True:
                chunk = handle.read(4096)
                if not chunk:
                    break
                yield chunk

    headers = {"X-Audio-Path": str(output_path.relative_to(ROOT_DIR))}
    return StreamingResponse(iter_chunks(), media_type="audio/wav", headers=headers)
