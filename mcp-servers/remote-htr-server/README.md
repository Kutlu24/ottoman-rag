# remote-htr-server

Kraken HTR'i **GPU'lu uzak bir makinede** çalıştırıp HTTP üzerinden sunan
küçük bir referans servis. `htr-server` (yerel, MCP/CPU) ile aynı
`kraken_runner.run_kraken()` fonksiyonunu kullanır — tek fark, ağ üzerinden
erişilebilir olması ve varsayılan cihazın `cuda:0` olması.

Bunu şu tür yerlere deploy edebilirsiniz:
- **Google Cloud Run + GPU** ([resmi rehber](https://cloud.google.com/run/docs/configuring/services/gpu))
- Üniversitenizin GPU sunucusu (Docker + NVIDIA Container Toolkit kuruluysa)
- Kendi GPU'lu makineniz

## Neden ayrı bir servis?

Yerel `htr-server` MCP protokolü (stdio) üzerinden çalışır — bu, aynı
makinedeki bir alt süreçle konuşmak için uygundur ama ağ üzerinden farklı
bir makineye bağlanmak için değil. `remote-htr-server` bunun yerine düz bir
HTTP uç noktası (`POST /run-htr`) sunar; backend, `HTR_MODE=remote`
ayarlandığında (veya `/ingest` isteğinde `htr_backend: "remote"`
belirtildiğinde) buraya bağlanır.

## Kurulum ve test (GPU olmadan, yerelde doğrulama için)

```
pip install -e ../../packages/ottoman_rag_common
pip install -e ../htr-server
pip install -e .

# GPU yoksa device'ı cpu'ya zorlayın (sadece uctan uca akışı test etmek için)
$env:KRAKEN_DEVICE = "cpu"
$env:KRAKEN_MODEL_DIR = "..\htr-server\models"
$env:KRAKEN_DEFAULT_MODEL = "ottoman_best.mlmodel"
uvicorn remote_htr_server.main:app --port 8080
```

Sonra backend'in `.env`'ine ekleyin:
```
HTR_MODE=remote
REMOTE_HTR_URL=http://localhost:8080
```

## Gerçek GPU sunucusuna deploy

`Dockerfile`'ı temel alıp:
1. `REMOTE_HTR_API_KEY`'i sunucunun secret/env değişkenlerinde belirleyin
   (internete açık olacaksa **zorunlu** — aksi halde herkes ücretsiz GPU
   kullanabilir).
2. `docker build` + Cloud Run/sunucunuza deploy edin.
3. Backend'in `.env`'inde `HTR_MODE=remote`, `REMOTE_HTR_URL=https://...`,
   `REMOTE_HTR_API_KEY=...` (aynı anahtar) ayarlayın.

**Not:** Bu `Dockerfile` gerçek bir GPU'da test edilmedi (proje CPU'lu bir
makinede geliştirildi) — resmi PyTorch CUDA imajını temel alan, iyi
gerekçelendirilmiş bir başlangıç şablonu. Deploy ederken build hatası
alırsanız (özellikle kraken'in bağımlılıkları), kök dizindeki `Dockerfile`
ve README'deki "kraken/torch sürüm çakışmaları" notlarına bakın — aynı
sınıf sorunlarla karşılaşabilirsiniz.
