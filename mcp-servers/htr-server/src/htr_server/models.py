from __future__ import annotations

from pydantic import BaseModel


class Point(BaseModel):
    x: float
    y: float


class BoundingBox(BaseModel):
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @classmethod
    def from_points(cls, points: list[Point]) -> "BoundingBox":
        xs = [p.x for p in points]
        ys = [p.y for p in points]
        return cls(x_min=min(xs), y_min=min(ys), x_max=max(xs), y_max=max(ys))


class Line(BaseModel):
    id: str
    text: str
    confidence: float | None = None
    polygon: list[Point]
    bbox: BoundingBox


class HtrPageResult(BaseModel):
    image_path: str
    model_used: str
    image_width: int | None = None
    image_height: int | None = None
    lines: list[Line]
