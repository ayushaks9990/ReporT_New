FROM node:20-alpine AS frontend-builder

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS application

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    EMBEDDING_CACHE_DIR=/app/.cache/fastembed \
    EMBEDDING_THREADS=1 \
    TOKENIZERS_PARALLELISM=false \
    PORT=10000

WORKDIR /app
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt
COPY . ./
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist

RUN python -m backend.embeddings
ENV EMBEDDING_LOCAL_FILES_ONLY=true

RUN useradd --create-home --uid 10001 analyticapp \
    && chown -R analyticapp:analyticapp /app

USER analyticapp
EXPOSE 10000
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000}"]
