from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from ottoman_rag_common.htr import HtrPageResult

from .kraken_runner import KrakenError, run_kraken

mcp = FastMCP("htr-server")

MODEL_DIR = Path(os.environ.get("KRAKEN_MODEL_DIR", Path(__file__).resolve().parents[2] / "models"))
DEFAULT_MODEL = os.environ.get("KRAKEN_DEFAULT_MODEL")
DEFAULT_DEVICE = os.environ.get("KRAKEN_DEVICE", "cpu")


@mcp.tool()
def list_models() -> list[str]:
    """models/ klasöründeki kullanılabilir Kraken .mlmodel dosyalarını listeler."""
    if not MODEL_DIR.exists():
        return []
    return sorted(p.name for p in MODEL_DIR.glob("*.mlmodel"))


@mcp.tool()
def run_htr(image_path: str, model_name: str | None = None, device: str | None = None) -> HtrPageResult:
    """Bir el yazması sayfa görüntüsünü segmentleyip tanır.

    Args:
        image_path: Sayfa görüntüsünün dosya yolu.
        model_name: models/ klasöründeki bir .mlmodel dosyasının adı.
            Verilmezse KRAKEN_DEFAULT_MODEL ortam değişkeni kullanılır.
        device: kraken'in -d/--device değeri ("cpu", "cuda:0" gibi).
            Verilmezse KRAKEN_DEVICE ortam değişkeni (varsayılan "cpu")
            kullanılır. Bu MCP sunucusu GPU'lu bir makinede/uzak sunucuda
            çalıştırılıyorsa "cuda:0" verilebilir.

    Returns:
        Satır bazlı metin, güven skoru ve bounding box (polygon) listesi
        içeren HtrPageResult.
    """
    chosen_model = model_name or DEFAULT_MODEL
    if not chosen_model:
        raise ValueError(
            "model_name verilmedi ve KRAKEN_DEFAULT_MODEL tanımlı değil. "
            f"Kullanılabilir modeller: {list_models()}"
        )

    model_path = MODEL_DIR / chosen_model
    try:
        return run_kraken(image_path, str(model_path), device=device or DEFAULT_DEVICE)
    except KrakenError as exc:
        raise RuntimeError(str(exc)) from exc


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
