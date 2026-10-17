# Speaking app: React build + FastAPI server with Whisper on an NVIDIA GPU.
# Used by docker-compose.yml; see docs/deployment.md.

# ----- Frontend: npm run build -> frontend/dist -----
FROM node:22.12.0-bookworm-slim AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ----- Backend -----
FROM python:3.11-slim-bookworm
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    # cuBLAS 12 + cuDNN 9 for ctranslate2 come from pip (requirements-gpu.txt), not from a CUDA base image
    LD_LIBRARY_PATH=/usr/local/lib/python3.11/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.11/site-packages/nvidia/cudnn/lib
# The project root is /app (config.ROOT_DIR): backend/, frontend/dist, data/, recordings/, certs/
WORKDIR /app/backend
COPY backend/requirements.txt backend/requirements-gpu.txt ./
RUN pip install -r requirements.txt -r requirements-gpu.txt
COPY backend/ ./
COPY --from=frontend /src/frontend/dist /app/frontend/dist
EXPOSE 8000
# python -m app reads SERVER_HOST/PORT and SSL_* (docker-compose.yml sets SERVER_HOST=0.0.0.0)
CMD ["python", "-m", "app"]
