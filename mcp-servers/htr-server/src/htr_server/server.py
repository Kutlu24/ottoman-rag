from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .kraken_runner import KrakenError, run_kraken
from .models import HtrPageResult

mcp = FastMCP("htr-server")

MODEL_DIR = Path(os.environ.get("KRAKEN_MODEL_DIR", Path(__file__).resolve().parents[2] / "models"))
DEFAULT_MODEL = os.environ.get("KRAKEN_DEFAULT_MODEL")


@mcp.tool()
def list_models() -> list[str]:
    """models/ klasöründeki kullanılabilir Kraken .mlmodel dosyalarını listeler."""
    if not MODEL_DIR.exists():
        return []
    return sorted(p.name for p in MODEL_DIR.glob("*.mlmodel"))


@mcp.tool()
def run_htr(image_path: str, model_name: str | None = None) -> HtrPageResult:
    """Bir el yazması sayfa görüntüsünü segmentleyip tanır.

    Args:
        image_path: Sayfa görüntüsünün dosya yolu.
        model_name: models/ klasöründeki bir .mlmodel dosyasının adı.
            Verilmezse KRAKEN_DEFAULT_MODEL ortam değişkeni kullanılır.

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
        return run_kraken(image_path, str(model_path))
    except KrakenError as exc:
        raise RuntimeError(str(exc)) from exc


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
