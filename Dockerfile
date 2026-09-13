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

COPY --chown=user packages/ottoman_rag_common ./packages/ottoman_rag_common
COPY --chown=user mcp-servers/htr-server ./mcp-servers/htr-server
COPY --chown=user mcp-servers/search-server ./mcp-servers/search-server
COPY --chown=user ingestion ./ingestion
COPY --chown=user backend ./backend

# torch icin acik bir surum+etiket sabitlemesi (ör. torch==2.14.0+cpu)
# denendi ama kraken'in kendi surum araligiyla (bazi kraken surumleri
# torch<=2.9 istiyor) cakisip "ResolutionImpossible" hatasi verdi. Bunun
# yerine, bu makinede DOGAL pip cozumlemesinin (hicbir sabitleme olmadan)
# zaten kendiliginden indigi surume (torch 2.14.0) guvenip sadece CPU
# tekerleklerini ek bir kaynak olarak sunuyoruz - PEP 440'a gore "+cpu"
# etiketli bir surum, ayni sürüm numarali etiketsiz (CUDA'li) surumden
# daha yuksek onceliklidir, bu yuzden pip kendiliginden CPU surumunu
# tercih eder.
#
# Kraken/htr-server ve search-server BILEREK IKI AYRI RUN'da kuruluyor:
# kraken 7.1.1 kendi paket metadata'sinda safetensors~=0.7.0 istiyor (bu,
# kraken'in kendi calisma zamani ihtiyaciyla - safetensors>=0.8.0 -
# celisen bir paketleme hatasi). Ikisini TEK cagrida kurmaya calismak
# pip'in bu celiskiyi yakalayip ResolutionImpossible vermesine yol
# aciyor. Ayri cagrilarda, search-server'in sentence-transformers/
# transformers'i kendi (daha yeni) safetensors ihtiyacini pip'in
# kraken'e karsi tekrar dogrulamadan kurabiliyor - bu makinede tum
# oturum boyunca organik olarak calisan durum tam buydu.
RUN pip install --no-cache-dir --user \
      --extra-index-url https://download.pytorch.org/whl/cpu \
      -e ./packages/ottoman_rag_common \
      -e ./mcp-servers/htr-server \
      -e ./ingestion \
      -e ./backend

RUN pip install --no-cache-dir --user \
      --extra-index-url https://download.pytorch.org/whl/cpu \
      -e ./mcp-servers/search-server

# Kraken Ottoman base modeli (OpenITI, Zenodo) - .gitignore'da oldugu icin
# repodan degil, build sirasinda dogrudan indirilir.
RUN mkdir -p mcp-servers/htr-server/models && \
    curl -fL --retry 5 --retry-all-errors --retry-delay 5 \
      -o mcp-servers/htr-server/models/ottoman_best.mlmodel \
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
