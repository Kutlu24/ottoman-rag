# htr-server

Kraken'i saran MCP sunucusu. Bir sayfa görüntüsü verildiğinde satır bazlı
segmentasyon + tanıma yapar, her satır için metin + confidence + bounding box
(polygon koordinatları, orijinal görüntü piksel uzayında) döndürür.

## Kurulum

```
cd mcp-servers/htr-server
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

## Model

`models/` klasörüne bir Kraken `.mlmodel` dosyası koyun. Başlangıç noktası olarak
OpenITI'nin Ottoman baskı base modelini kullanabilirsiniz:
https://zenodo.org/records/7050342

El yazması üzerinde doğruluk düşükse `training/` altındaki fine-tuning script'i ile
kendi ground-truth verinizle bu modeli fine-tune edin.

## Çalıştırma (bağımsız test)

```
python -m htr_server.server
```

Claude Code / Claude Desktop gibi bir MCP client'a bağlamak için `.mcp.json`'a
bu sunucunun komutunu ekleyin (proje kökünde ileride ekleyeceğiz).

## Tool'lar

- `list_models()` — `models/` klasöründeki kullanılabilir `.mlmodel` dosyalarını listeler.
- `run_htr(image_path, model_name=None)` — görüntüyü segmentleyip tanır, satır listesi
  (`text`, `confidence`, `bbox`) döndürür.
