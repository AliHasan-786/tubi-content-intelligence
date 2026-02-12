# syntax=docker/dockerfile:1

FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json ./
# No lockfile checked in yet; prefer deterministic installs later.
RUN npm install
COPY frontend/ ./
RUN npm run build


FROM python:3.11-slim AS backend
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY scripts/ scripts/
COPY prompts/ prompts/
COPY Tubi-Data.csv Tubi-Data.csv
COPY Tubi_with_Personas_and_Clusters.csv Tubi_with_Personas_and_Clusters.csv

RUN mkdir -p data frontend/dist
RUN python scripts/prepare_data.py --raw Tubi-Data.csv --persona Tubi_with_Personas_and_Clusters.csv --out data/clean_titles.csv
# Build embeddings at image build time so the first request is fast.
RUN python scripts/build_embeddings.py --clean data/clean_titles.csv --out data/embeddings.npy --meta data/embeddings_meta.json

COPY --from=frontend /app/frontend/dist frontend/dist

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

