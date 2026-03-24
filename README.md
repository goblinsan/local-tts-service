# local-tts-service

Local/offline HTTP TTS service (FastAPI) with voice management, static local UI, and Windows detached startup scripts.

## What this service provides

- TTS generation as WAV files (`POST /tts`, `POST /tts/stream`)
- Voice library management on local disk (`GET/POST/PATCH/DELETE /voices...`)
- Browser UI at `/` (redirects to `/static/index.html`) for testing TTS and managing voices
- Runtime diagnostics endpoint (`GET /runtime`) for CPU/CUDA visibility
- Admin cleanup endpoint for generated outputs (`DELETE /admin/generated/files`)
- Rolling log files with retention controls

## Prerequisites

- Python 3.10+ (3.11 recommended for current F5-TTS/Torch compatibility)
- FFmpeg available on PATH for voice creation/upload normalization
	- On Windows, a shared build is recommended (e.g. `Gyan.FFmpeg.Shared`) so dependent DLLs resolve correctly.

## Quick start

1. Create/activate your environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the API from repo root:

```bash
python -m apps.api.run
```

4. Open:
	 - UI: `http://localhost:5000/`
	 - Health: `http://localhost:5000/health`

## API summary

- `GET /health` - basic liveness check.
- `GET /runtime` - runtime info (`device`, `cuda_available`, `torch_version`).
- `GET /voices` - list voices from `voices/<voice_id>/metadata.json`.
- `POST /voices` - create voice from uploaded reference audio (normalizes to mono 24k WAV).
- `POST /voices/create` - alias for `POST /voices`.
- `PATCH /voices/{voice_id}` - update voice metadata (`name`, `description`, `transcript`).
- `DELETE /voices/{voice_id}` - delete one voice directory.
- `POST /tts` - generate WAV and return file response.
- `POST /tts/stream` - generate WAV and stream bytes.
- `DELETE /admin/generated/files` - delete files inside `generated/` (does not remove the directory).

### Generate speech example

```bash
curl -X POST http://localhost:5000/tts \
	-H "content-type: application/json" \
	-d '{
		"text": "Hello, this is your assistant.",
		"voice": "assistant_v1",
		"format": "wav"
	}' \
	--output out.wav -i
```

Response includes `X-Audio-Path` with the generated file location under `generated/`.

### Create voice example

```bash
curl -X POST http://localhost:5000/voices \
	-F "reference_audio=@sample.wav" \
	-F "name=Assistant Voice v2" \
	-F "description=Neutral helpful assistant" \
	-F "source=recorded" \
	-F "transcript=Hello, this is a sample of my voice"
```

### Update transcript example

```bash
curl -X PATCH http://localhost:5000/voices/assistant_v1 \
	-H "content-type: application/json" \
	-d '{"transcript":"Hello, this is a sample of my voice"}'
```

### Clear generated files example

```bash
curl -X DELETE http://localhost:5000/admin/generated/files
```

## Voice data requirements

- Each voice is stored at `voices/<voice_id>/`.
- Required files/fields for reliable TTS:
	- `sample.wav` (non-empty, normalized WAV)
	- `metadata.json` with `transcript`
- TTS requests are rejected if transcript metadata is missing.

## Local UI

The built-in page (`/`) supports:

- Listing/selecting/deleting voices
- Editing and saving per-voice transcript metadata
- Creating voices via audio upload
- Running TTS tests with standard and fast mode
- Clearing generated files via admin maintenance action
- Viewing runtime mode (CPU/CUDA) in header

## Configuration

`config/default.json` controls F5 settings.

Current pattern:

```json
{
	"f5tts": {
		"command": null,
		"inference": {
			"nfe_step": 28,
			"speed": 0.95,
			"cfg_strength": 2.2
		}
	}
}
```

- `command: null` uses in-process generation.
- If you set `command`, it should accept a payload JSON path as final arg and write output WAV to `output_path`.

## Logs and retention

- Logs are written to `logs/app.log` and `logs/access.log`.
- Rotation triggers on either condition:
	- every 2 days, or
	- file size >= 10 MB
- Retention/purge defaults:
	- keep up to 5 rotated files
	- delete archives older than 10 days
	- cap rotated archive size at 200 MB per stream

## Windows persistent run (outside VS Code)

Install startup launcher (current user):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/windows/install-startup.ps1
```

Start detached now:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/windows/start-detached.ps1
```

Remove startup launcher:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/windows/uninstall-startup.ps1
```

`start-detached.ps1` chooses Python env in this order when present:

1. `.venv311cuda`
2. `.venv311`
3. `.venv`

## Project layout

```text
local-tts-service/
	apps/
		api/
			main.py
			run.py
			static/
				index.html
	services/
		f5tts/
	voices/
	generated/
	logs/
	scripts/
		windows/
	infra/
	config/
		default.json
```
