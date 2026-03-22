# local-tts-service

Local, offline Text-to-Speech service with a clean HTTP boundary for agents and gateway integration.

## Implemented features

- `POST /tts` generates and returns a WAV file.
- `POST /tts/stream` streams WAV bytes.
- `GET /voices` lists versioned local voices.
- `POST /voices` creates a new voice from reference audio.
- `POST /voices/create` alias for voice creation pipeline compatibility.
- `DELETE /voices/{id}` removes a voice.
- `GET /health` basic health probe.

## Project layout

```text
local-tts-service/
	apps/
		api/
			main.py
	services/
		f5tts/
			engine.py
	voices/
		assistant_v1/
			sample.wav
			metadata.json
	generated/
	scripts/
	infra/
		docker/
		systemd/
	config/
		default.json
```

## Quick start

1. Create and activate a Python environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the API from repo root:

```bash
python -m apps.api.run
```

4. Verify health:

```bash
curl http://localhost:5000/health
```

## API examples

### List voices

```bash
curl http://localhost:5000/voices
```

### Generate speech

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

Response includes `X-Audio-Path` header pointing to the stored file under `generated/`.

### Stream speech

```bash
curl -X POST http://localhost:5000/tts/stream \
	-H "content-type: application/json" \
	-d '{
		"text": "Streaming demo",
		"voice": "assistant_v1",
		"format": "wav"
	}' \
	--output stream.wav -i
```

### Create voice

```bash
curl -X POST http://localhost:5000/voices \
	-F "reference_audio=@sample.wav" \
	-F "name=Assistant Voice v2" \
	-F "description=Neutral helpful assistant" \
	-F "source=recorded"
```

## F5-TTS integration hook

`services/f5tts/engine.py` supports an external command hook via `config/default.json`:

```json
{
	"f5tts": {
		"command": ["python", "services/f5tts/your_f5_runner.py"]
	}
}
```

The command receives a temporary payload JSON path as its final argument and should write WAV to `output_path`.

If no command is configured, the service uses a deterministic local fallback WAV generator so APIs remain functional offline.

## Notes

- Service boundary remains clean: agents call HTTP API only.
- Voices are file-based data in `voices/`.
- Service is stateless per request.
- Logs write to `logs/app.log` and `logs/access.log`.
- Log rotation policy is enforced as: rotate after 2 days or 10MB, whichever happens first.
- Rolled logs auto-purge (default): keep up to 5 rotated files, max age 10 days, and max 200MB of archives per log stream.
