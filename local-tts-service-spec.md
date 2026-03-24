# Project: local-tts-service

## Purpose

A local Text-to-Speech service that:

- Provides an HTTP API for agents to generate speech
- Supports voice cloning (F5-TTS)
- Manages a versioned voice library
- Integrates with the home gateway + agent system
- Runs entirely locally (no external APIs)

---

## Core Capabilities

### 1. TTS Generation API

Input:
- text
- voice_id
- optional style params

Output:
- audio file (wav/stream)

Example:

POST /tts
{
  "text": "Hello, this is your assistant.",
  "voice": "assistant_v1",
  "format": "wav"
}

---

### 2. Voice Library

Stored in repo or mounted volume:

/voices/
  assistant_v1/
    sample.wav
    metadata.json
  narrator_v1/
    sample.wav
    metadata.json

metadata.json example:

{
  "name": "Assistant Voice",
  "description": "Neutral helpful assistant",
  "source": "recorded",
  "created_at": "2026-03-22"
}

---

### 3. Voice Creation Pipeline

Endpoint:

POST /voices/create

Input:
- reference_audio
- optional transcript

Output:
- new voice_id stored in /voices/

---

### 4. Streaming Support (optional but recommended)

POST /tts/stream

- streams audio chunks back
- useful for real-time agent interaction

---

## Architecture

Agent (UI / backend)
        ↓
Gateway API (chat router)
        ↓
TTS Service (this repo)
        ↓
F5-TTS engine
        ↓
Audio output (file or stream)

---

## Tech Stack (recommended for your setup)

### Option A — Fastest path (recommended)
- Node.js + TypeScript (API layer)
- Python (F5-TTS execution layer)

### Option B — Pure Python
- FastAPI
- simpler but less aligned with your TS stack

---

## Suggested Structure

local-tts-service/
  apps/
    api/                # Node or FastAPI server
  services/
    f5tts/             # model wrapper
  voices/
  scripts/
    record-sample.sh
    normalize-audio.sh
  infra/
    docker/
    systemd/
  config/
    default.json

---

## F5-TTS Integration Layer

Responsibilities:
- load model
- accept:
  - text
  - reference audio
- generate waveform
- return file or buffer

Example interface:

generateSpeech({
  text,
  voicePath,
  outputPath
})

---

## Deployment Model

### Runs on:
- one of your local machines (GPU preferred)

### Exposed via:
- internal LAN (e.g. http://tts.local:5000)
- optionally proxied via gateway

### Deployment:
- GitHub → merge to main
- gateway runner pulls + deploys
- same pipeline as your apps

---

## API Design

### Generate speech
POST /tts

### Stream speech
POST /tts/stream

### List voices
GET /voices

### Create voice
POST /voices

### Delete voice
DELETE /voices/:id

---

## Integration with Agents

Example:

await tts.generate({
  text: response,
  voice: "assistant_v1"
})

Or:

agent = {
  model: "qwen",
  voice: "narrator_v2"
}

---

## Future Extensions

- voice styles (happy, serious, whisper)
- voice versioning
- caching generated audio
- multi-language support
- WebRTC streaming
- integration with home automation / speakers
- ElevenLabs fallback (optional)

---

## Key Design Decisions

### 1. Voices are data, not config
- stored as files
- versioned in git or storage

### 2. TTS is stateless
- no session required
- just input → output

### 3. Service boundary is clean
- agents do NOT call F5 directly
- everything goes through API

### 4. Works offline
- no cloud dependency

---

## Minimal MVP

Build this first:

- [ ] /tts endpoint
- [ ] single voice support
- [ ] F5-TTS integration
- [ ] save output wav
- [ ] simple curl test

Then expand.

---

## Mental Model

This service is:

"The voice layer of your local AI stack — just like LM Studio is the thinking layer."
