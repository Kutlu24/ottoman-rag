from __future__ import annotations

from pydantic import BaseModel


class Point(BaseModel):
    x: float
    y: float


class BoundingBox(BaseModel):
    """Orijinal sayfa görüntüsü piksel uzayında bounding box.

    Highlight overlay bu koordinatları doğrudan kullanır; bu yüzden HTR
    backend'i (Kraken/Transkribus) ne olursa olsun bu şekle normalize edilir.
    """

    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @classmethod
    def from_points(cls, points: list[Point]) -> "BoundingBox":
        xs = [p.x for p in points]
        ys = [p.y for p in points]
        return cls(x_min=min(xs), y_min=min(ys), x_max=max(xs), y_max=max(ys))

    @classmethod
    def union(cls, boxes: list["BoundingBox"]) -> "BoundingBox":
        return cls(
            x_min=min(b.x_min for b in boxes),
            y_min=min(b.y_min for b in boxes),
            x_max=max(b.x_max for b in boxes),
            y_max=max(b.y_max for b in boxes),
        )
