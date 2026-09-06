"""PAGE XML parsing, isim alanindan bagimsiz (kraken surumleri arasinda
PAGE XML sema versiyonu degisebiliyor, bu yuzden namespace'i yok sayip
local tag adlarina gore parse ediyoruz)."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from .models import BoundingBox, HtrPageResult, Line, Point


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find_local(elem: ET.Element, name: str) -> ET.Element | None:
    for child in elem:
        if _local(child.tag) == name:
            return child
    return None


def _findall_local(elem: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in elem.iter() if _local(child.tag) == name]


def _parse_points(points_attr: str) -> list[Point]:
    points: list[Point] = []
    for pair in points_attr.strip().split():
        x_str, y_str = pair.split(",")
        points.append(Point(x=float(x_str), y=float(y_str)))
    return points


def parse_page_xml(xml_path: str, image_path: str, model_used: str) -> HtrPageResult:
    tree = ET.parse(xml_path)
    root = tree.getroot()

    page_elem = _find_local(root, "Page")
    width = height = None
    if page_elem is not None:
        width = int(page_elem.attrib["imageWidth"]) if "imageWidth" in page_elem.attrib else None
        height = int(page_elem.attrib["imageHeight"]) if "imageHeight" in page_elem.attrib else None

    lines: list[Line] = []
    for line_elem in _findall_local(root, "TextLine"):
        coords_elem = _find_local(line_elem, "Coords")
        if coords_elem is None or "points" not in coords_elem.attrib:
            continue
        polygon = _parse_points(coords_elem.attrib["points"])
        if not polygon:
            continue

        text_equiv = _find_local(line_elem, "TextEquiv")
        text = ""
        confidence = None
        if text_equiv is not None:
            unicode_elem = _find_local(text_equiv, "Unicode")
            text = (unicode_elem.text or "") if unicode_elem is not None else ""
            conf_attr = text_equiv.attrib.get("conf")
            confidence = float(conf_attr) if conf_attr is not None else None

        lines.append(
            Line(
                id=line_elem.attrib.get("id", f"line_{len(lines)}"),
                text=text,
                confidence=confidence,
                polygon=polygon,
                bbox=BoundingBox.from_points(polygon),
            )
        )

    return HtrPageResult(
        image_path=image_path,
        model_used=model_used,
        image_width=width,
        image_height=height,
        lines=lines,
    )
