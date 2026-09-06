# GPU'lu uzak bir makineye (Google Cloud Run + GPU, universite GPU
# sunucusu, kendi GPU'lu sunucunuz) deploy etmek icin sablon.
#
# ONEMLI: Bu Dockerfile gercek bir GPU olmadan test edilemedi (bu proje
# CPU'lu bir gelistirme makinesinde yazildi). Resmi PyTorch CUDA imajini
# temel aliyoruz ki torch zaten dogru CUDA surumuyle gelsin - kraken'i
# kurarken pip'in torch'u degistirmemesine dikkat edin (bkz. kok dizindeki
# Dockerfile'daki benzer not: kraken/sentence-transformers'i AYRI pip
# cagrilarinda kurmak, versiyon celismelerini onluyor).
#
# Google Cloud Run + GPU icin: https://cloud.google.com/run/docs/configuring/services/gpu
FROM pytorch/pytorch:2.9.0-cuda12.6-cudnn9-runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY packages/ottoman_rag_common ./packages/ottoman_rag_common
COPY mcp-servers/htr-server ./mcp-servers/htr-server
COPY mcp-servers/remote-htr-server ./mcp-servers/remote-htr-server

# Temel imajda CUDA'li torch zaten var; kraken'i --no-deps ile kurup
# gercekten eksik olan diger bagimliliklarini ayri ekliyoruz - boylece pip
# torch'u degistirmeye (ve CPU/farkli CUDA surumune dusurmeye) calismiyor.
RUN pip install --no-cache-dir \
      -e ./packages/ottoman_rag_common \
      -e ./mcp-servers/htr-server --no-deps \
      -e ./mcp-servers/remote-htr-server \
    && pip install --no-cache-dir \
      "kraken==7.1.1" --no-deps \
    && pip install --no-cache-dir \
      click safetensors coremltools htrmopo iso639-lang jinja2 jsonschema \
      lightning lxml numpy packaging pillow platformdirs protobuf pyarrow \
      regex requests rich scikit-image scipy shapely threadpoolctl \
      pytorch-lightning python-bidi tifffile torchvision tqdm

# Kraken modeli - build sirasinda indirilir (repoda .gitignore'da).
RUN mkdir -p models && \
    curl -fL -o models/ottoman_best.mlmodel \
      "https://zenodo.org/records/7050342/files/ottoman_best.mlmodel?download=1"

ENV KRAKEN_MODEL_DIR=/app/models \
    KRAKEN_DEFAULT_MODEL=ottoman_best.mlmodel \
    KRAKEN_DEVICE=cuda:0 \
    PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8

# REMOTE_HTR_API_KEY: Cloud Run/sunucu secrets'inda ayarlayin - bu servis
# internete acik olacaksa MUTLAKA doldurulmali.

EXPOSE 8080
CMD ["uvicorn", "remote_htr_server.main:app", "--host", "0.0.0.0", "--port", "8080", "--app-dir", "mcp-servers/remote-htr-server/src"]
