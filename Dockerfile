# Debate Analyzer – AWS Batch GPU image (faster-whisper + pyannote + video downloader)
# Base: NVIDIA CUDA + cuDNN for GPU transcription
ARG CUDA_VERSION=12.1.0-cudnn8-runtime-ubuntu22.04
FROM nvidia/cuda:${CUDA_VERSION}

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# System deps: Python 3.10, ffmpeg, AWS CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3.10-venv \
    python3-pip \
    ffmpeg \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.10 /usr/bin/python

# Install AWS CLI v2 (for S3 sync in entrypoint)
RUN curl -sS "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip \
    && unzip -q /tmp/awscliv2.zip -d /tmp \
    && /tmp/aws/install -b /usr/local/bin \
    && rm -rf /tmp/awscliv2.zip /tmp/aws

# Install Deno (JS runtime required by yt-dlp for YouTube EJS challenges)
RUN curl -fsSL https://deno.land/install.sh | sh \
    && mv /root/.deno/bin/deno /usr/local/bin/ \
    && rm -rf /root/.deno

WORKDIR /app

# Copy project and install Python deps (no dev deps)
COPY pyproject.toml poetry.lock* README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# Pipeline entrypoint (download -> S3 -> transcribe -> S3)
COPY deploy/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
