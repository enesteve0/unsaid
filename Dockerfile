# syntax=docker/dockerfile:1
# Unsaid: one linux/amd64 image with the web app, the API and NVIDIA Parakeet speech recognition.
# Build on Apple Silicon with: docker buildx build --platform linux/amd64 -t unsaid .

FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY web/package.json web/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    ASR_THREADS=2 DATA_DIR=/data SAMPLES_DIR=/app/samples
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.9.27 /uv /usr/local/bin/uv
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
RUN uv sync --frozen --no-dev
# Bake NVIDIA Parakeet TDT 0.6B v2 (int8 ONNX, CC-BY-4.0) and Silero VAD into the image: nothing downloads at boot.
RUN uv run --no-sync python -c "import onnx_asr as o; o.load_vad('silero', 'models/silero'); o.load_model('nemo-parakeet-tdt-0.6b-v2', 'models/parakeet-v2', quantization='int8')"
COPY samples/ /app/samples/
COPY --from=web /web/dist /app/web/dist
EXPOSE 8080
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=4)"
CMD ["uv", "run", "--no-sync", "python", "-c", "from unsaid.api import main; main()"]
