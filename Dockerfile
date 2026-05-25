# syntax=docker/dockerfile:1.7
#
# local-tts-service container image.
#
# Targets RTX 50-series (Blackwell, sm_120) hosts running NVIDIA driver
# >= 580 with CUDA 13 runtime. The runtime image ships the CUDA + cuDNN
# user-space libraries; the kernel-side driver must be installed on the
# host and exposed via `nvidia-container-toolkit` (`runtime: nvidia`).
FROM nvidia/cuda:13.0.1-cudnn-runtime-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/cache/huggingface \
    TORCH_HOME=/cache/torch \
    TTS_CLEANUP_ENABLED=1 \
    TTS_CLEANUP_MAX_AGE_HOURS=24 \
    TTS_CLEANUP_INTERVAL_MINUTES=60

# System deps: python 3.11 (via deadsnakes), ffmpeg, build tooling for any
# packages without prebuilt wheels.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg software-properties-common \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        python3.11 python3.11-venv python3.11-dev \
        ffmpeg git \
        build-essential \
    && curl -fsSL https://bootstrap.pypa.io/get-pip.py | python3.11 \
    && ln -sf /usr/bin/python3.11 /usr/local/bin/python \
    && ln -sf /usr/bin/python3.11 /usr/local/bin/python3 \
    && apt-get purge -y software-properties-common gnupg \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install PyTorch + torchaudio with CUDA 13 wheels first so this layer
# caches independently of the application code.
RUN python -m pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cu130 \
        "torch==2.12.0+cu130" "torchaudio==2.11.0+cu130"

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .

# Runtime working dirs (also intended to be bind-mounted as volumes so
# voices + generated audio survive container rebuilds).
RUN mkdir -p /app/voices /app/generated /app/logs /cache/huggingface /cache/torch

EXPOSE 5000

CMD ["python", "-m", "apps.api.run"]
