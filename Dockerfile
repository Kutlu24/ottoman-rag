# --- Asama 1: frontend build ---
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Asama 2: calisma zamani imaji ---
FROM python:3.11-slim

# Turkce/Osmanlica metin ve Kraken'in kendi ilerleme ciktisi icin UTF-8
# zorunlu (Windows'ta ayni sinif bir UnicodeEncodeError hatasi yasandi,
# bkz. proje README'sindeki gelistirme gunlugu - Linux'ta varsayilan
# locale yine de guvenli tarafta kalmak icin acikca ayarlaniyor).
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONUNBUFFERED=1

# curl: Kraken model dosyasini indirmek icin (asagida), root iken kurulmali
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH
WORKDIR $HOME/app

RUN pip install --no-cache-dir --upgrade pip

# CPU-only torch onceden kurulur ki kraken'in kendi bagimliligi CUDA'li
# bir surumu cekmeye calismasin (image boyutu + build suresi icin onemli).
# Surum, bu makinede dogrulanmis calisan kombinasyonla eslesecek sekilde
# sabitlendi (bkz. search-server/pyproject.toml'daki transformers notu).
RUN pip install --no-cache-dir --user torch==2.14.0 --index-url https://download.pytorch.org/whl/cpu

COPY --chown=user packages/ottoman_rag_common ./packages/ottoman_rag_common
COPY --chown=user mcp-servers/htr-server ./mcp-servers/htr-server
COPY --chown=user mcp-servers/search-server ./mcp-servers/search-server
COPY --chown=user ingestion ./ingestion
COPY --chown=user backend ./backend

RUN pip install --no-cache-dir --user \
      -e ./packages/ottoman_rag_common \
      -e ./mcp-servers/htr-server \
      -e ./mcp-servers/search-server \
      -e ./ingestion \
      -e ./backend

# Kraken Ottoman base modeli (OpenITI, Zenodo) - .gitignore'da oldugu icin
# repodan degil, build sirasinda dogrudan indirilir.
RUN mkdir -p mcp-servers/htr-server/models && \
    curl -fL -o mcp-servers/htr-server/models/ottoman_best.mlmodel \
      "https://zenodo.org/records/7050342/files/ottoman_best.mlmodel?download=1"

# Embedding modelini (~1GB) runtime'da degil build'de indirip HF Hub
# cache'ine yerlestiriyoruz - aksi halde container her yeniden basladiginda
# (ornegin uykuya dalip uyandiginda) ilk sorgu cok yavas olurdu.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-base')"

COPY --chown=user --from=frontend-build /app/frontend/dist ./frontend/dist

ENV KRAKEN_MODEL_DIR=$HOME/app/mcp-servers/htr-server/models \
    KRAKEN_DEFAULT_MODEL=ottoman_best.mlmodel \
    EMBEDDING_MODEL_NAME=intfloat/multilingual-e5-base

EXPOSE 7860

# Shell form (JSON-array degil) kasitli: $PORT genisletmesi icin bir kabuk
# gerekiyor. HF Spaces sabit 7860 (app_port) bekler ve PORT ayarlamaz -
# ${PORT:-7860} bu durumda 7860'a duser. Render (ve benzeri platformlar)
# PORT'u dinamik olarak enjekte eder - ayni Dockerfile ikisinde de degisiklik
# gerektirmeden calisir.
CMD python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-7860} --app-dir backend/src
