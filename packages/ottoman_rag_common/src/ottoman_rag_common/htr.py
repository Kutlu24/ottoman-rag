from __future__ import annotations

from pydantic import BaseModel

from .geometry import BoundingBox, Point


class Line(BaseModel):
    id: str
    text: str
    confidence: float | None = None
    polygon: list[Point]
    bbox: BoundingBox


class HtrRun(BaseModel):
    """Bir HTR calismasinin kimligi - hangi backend/model, hangi surum.

    Chunk'lara tasinir ki arastirmaci hangi transkripsiyonun hangi modelden
    geldigini (ve dolayisiyla ne kadar guvenilir oldugunu) gorebilsin.
    """

    htr_run_id: str
    backend: str  # "kraken" | "transkribus"
    model_name: str
    model_ref: str | None = None  # ör. Transkribus htrId, Kraken .mlmodel dosya adı
    cer_estimate: float | None = None  # modelin yayınlanmış CER'i, biliniyorsa


class HtrPageResult(BaseModel):
    """Kraken ve Transkribus çıktılarının ortak normalize edilmiş şekli."""

    image_path: str
    image_width: int | None = None
    image_height: int | None = None
    htr_run: HtrRun
    lines: list[Line]
