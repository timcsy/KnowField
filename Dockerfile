# KnowField 容器映像（vision 階段 27 PWA ＋ 34/35 部署）。
# 多階段：① node build 前端 dist；② python 執行期，editable 安裝（保留 src 佈局讓 _DIST 正確解析）。

# ── 前端 build ──
FROM node:20-alpine AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build          # → /fe/dist

# ── 後端執行期 ──
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 KNOWFIELD_MEDIA=/data/media
WORKDIR /app

# 先裝相依（利用快取）：只 copy pyproject＋src
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e ".[web]"

# 前端 dist 放在 _DIST 期望的位置（parents[3]/frontend/dist ＝ /app/frontend/dist）
COPY --from=frontend /fe/dist ./frontend/dist

# 非 root 執行；media 目錄（PVC 掛載點）可寫
RUN useradd -u 10001 -m app && mkdir -p /data/media && chown -R app:app /data
USER app

EXPOSE 8000
CMD ["uvicorn", "knowfield.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
