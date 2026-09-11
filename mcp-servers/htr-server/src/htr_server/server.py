from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from ottoman_rag_common.htr import HtrPageResult

from .hybrid_runner import run_hybrid_htr
from .kraken_runner import KrakenError, run_kraken

mcp = FastMCP("htr-server")

MODEL_DIR = Path(os.environ.get("KRAKEN_MODEL_DIR", Path(__file__).resolve().parents[2] / "models"))
DEFAULT_MODEL = os.environ.get("KRAKEN_DEFAULT_MODEL")
DEFAULT_DEVICE = os.environ.get("KRAKEN_DEVICE", "cpu")

# Kutlu24'un kendi egittigi CRNN modeli - OPSIYONEL bir tanima motoru
# (htr_engine="crnn_v2" ile secilir). Varsayilan hala saf Kraken akisi:
# gercek bir tarihi el yazmasi (ferman) uzerinde denendiginde CRNN modeli
# net biçimde kotu sonuc verdi (muhtemelen egitim verisinin - "Osmanli
# Turkcesine Giris" ders kitabi tarzi, temiz/basili metin - kapsami
# disinda kaldigi icin); temiz/basili Osmanlica metinlerde ise gercekten
# iyi calisti. Bu yuzden varsayilan olarak degil, bilinçli bir secim
# olarak sunuluyor - bkz. hybrid_runner.py.
CRNN_DIR = Path(__file__).resolve().parents[2] / "models" / "crnn_v2"
CRNN_CHECKPOINT = os.environ.get("CRNN_CHECKPOINT_PATH", str(CRNN_DIR / "ocr_resumed_20260911_1053_best.pth"))
CRNN_CHARSET = os.environ.get("CRNN_CHARSET_PATH", str(CRNN_DIR / "charset.json"))
CRNN_DEVICE = os.environ.get("CRNN_DEVICE", "cpu")


@mcp.tool()
def list_models() -> list[str]:
    """models/ klasöründeki kullanılabilir Kraken .mlmodel dosyalarını listeler."""
    if not MODEL_DIR.exists():
        return []
    return sorted(p.name for p in MODEL_DIR.glob("*.mlmodel"))


@mcp.tool()
def run_htr(
    image_path: str,
    model_name: str | None = None,
    device: str | None = None,
    htr_engine: str = "kraken",
) -> HtrPageResult:
    """Bir el yazması sayfa görüntüsünü segmentleyip tanır.

    Args:
        image_path: Sayfa görüntüsünün dosya yolu.
        model_name: models/ klasöründeki bir .mlmodel dosyasının adı
            (yalnızca htr_engine="kraken" iken kullanılır). Verilmezse
            KRAKEN_DEFAULT_MODEL ortam değişkeni kullanılır.
        device: Kraken segmentasyonu ve/veya CRNN tanıma için cihaz
            ("cpu", "cuda:0" gibi). Verilmezse KRAKEN_DEVICE/CRNN_DEVICE
            ortam değişkenleri (varsayılan "cpu") kullanılır.
        htr_engine: "kraken" (varsayılan) - Kraken'in kendi segment+ocr
            hattı, .mlmodel dosyasıyla. "crnn_v2" - deneysel: segmentasyonu
            yine Kraken yapar ama tanımayı Kutlu24'un kendi eğittiği CRNN
            modeli yapar (bkz. hybrid_runner.py). Temiz/basılı Osmanlıca
            metinlerde iyi sonuç verdiği doğrulandı; gerçek tarihi el
            yazması belgelerde (ör. ferman) henüz zayıf - kullanıcı
            bilinçli olarak seçmeli, varsayılan değil.

    Returns:
        Satır bazlı metin, güven skoru ve bounding box (polygon) listesi
        içeren HtrPageResult.
    """
    try:
        if htr_engine == "crnn_v2":
            return run_hybrid_htr(
                image_path,
                checkpoint_path=CRNN_CHECKPOINT,
                charset_path=CRNN_CHARSET,
                device=device or CRNN_DEVICE,
            )
        chosen_model = model_name or DEFAULT_MODEL
        if not chosen_model:
            raise ValueError(
                "model_name verilmedi ve KRAKEN_DEFAULT_MODEL tanımlı değil. "
                f"Kullanılabilir modeller: {list_models()}"
            )
        model_path = MODEL_DIR / chosen_model
        return run_kraken(image_path, str(model_path), device=device or DEFAULT_DEVICE)
    except KrakenError as exc:
        raise RuntimeError(str(exc)) from exc


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
