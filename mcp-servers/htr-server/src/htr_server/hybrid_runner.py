"""Hibrit HTR akisi: satir segmentasyonunu Kraken yapar, tanimayi
Kutlu24'un kendi egittigi CRNN modeli (crnn_model.py) yapar.

Neden hibrit: CRNN modeli sadece onceden kirpilmis tek-satir goruntuleri
tanir, tam bir sayfada satirlarin nerede oldugunu bulamaz (segmentasyon
yapamaz). Kraken'in "segment -bl" adimi bu segmentasyonu yapar; "ocr"
adimini ATLAYIP (bkz. kraken_runner.run_kraken(segment_only=True)) bos
metinli Line nesneleri elde ederiz, sonra her birinin bbox'ini orijinal
goruntuden kirpip CRNN modeliyle tek tek tanimlariz."""

from __future__ import annotations

from pathlib import Path

from ottoman_rag_common.geometry import BoundingBox
from ottoman_rag_common.htr import HtrPageResult, HtrRun, Line
from PIL import Image

from .crnn_model import CrnnRecognizer
from .kraken_runner import KrakenError, run_kraken

_recognizer: CrnnRecognizer | None = None


def group_fragments_into_lines(lines: list[Line]) -> list[list[Line]]:
    """Kraken parcalarini yaklasik satir gruplarina ayirir.

    Kraken'in genel-amaçli blla segmentasyonu bu belgelerde tam satirlar
    degil, harf/kelime parcalari uretiyor (gercek bir manuscript sayfasinda
    dogrulandi: 98 parca, cogu tek karakter) - CRNN modeli ise uzun tam
    satirlar uzerinde egitildi. Ilk denenen yaklasim (ikili dikey-kesisim
    orani + union-find transitif kapanis) zincirleme asiri-birlesmeye yol
    acti: birbiriyle örtüsen parcalar zincirlenerek birden fazla gercek
    satiri TEK bir dev bloka (ör. yukseklik 525px, sayfa 2000px'in
    ceyregi) birlestirdi. Bunun yerine: parcalari dikey merkezlerine gore
    SIRALAYIP, ardisik parcalar arasindaki dikey bosluk sayfadaki
    TIPIK parca yuksekligine (medyan) gore kucukse ayni gruba, degilse
    yeni gruba ekleyen tek-gecisli (1D) bir tarama kullaniyoruz - zincirleme
    asiri-birlesme riski yok, cunku her karar sadece komsu ciftler arasinda
    verilir, transitif kapanis alinmiyor."""
    if not lines:
        return []

    heights = [ln.bbox.y_max - ln.bbox.y_min for ln in lines if ln.bbox.y_max > ln.bbox.y_min]
    median_height = sorted(heights)[len(heights) // 2] if heights else 20.0
    # Ayni satirdaki parcalarin merkezleri birbirine yakin olmali (tipik
    # yukseklikle kiyaslanarak); bu esigin uzerindeki bosluk yeni bir satir
    # basladigini gosterir. 0.6 katsayisi deneysel - cok kucuk olursa tek
    # satirdaki harfler bile ayrilir, cok buyuk olursa komsu satirlar birlesir.
    gap_threshold = median_height * 0.6

    ordered = sorted(lines, key=lambda ln: (ln.bbox.y_min + ln.bbox.y_max) / 2)
    groups: list[list[Line]] = [[ordered[0]]]
    prev_center = (ordered[0].bbox.y_min + ordered[0].bbox.y_max) / 2
    for ln in ordered[1:]:
        center = (ln.bbox.y_min + ln.bbox.y_max) / 2
        if center - prev_center <= gap_threshold:
            groups[-1].append(ln)
        else:
            groups.append([ln])
        prev_center = center

    # Her grubu bbox x_min'e gore siralamak sadece union bbox hesabi icin
    # onemli - CRNN modeli kirpilan tek gorüntüyü kendisi (sagdan sola
    # yazim yonüne gore egitilmis haliyle) okuyor, parca sirasi metin
    # birlestirme icin kullanilmiyor.
    return [sorted(group, key=lambda ln: ln.bbox.x_min) for group in groups]


def get_recognizer(checkpoint_path: str, charset_path: str, device: str = "cpu") -> CrnnRecognizer:
    """CrnnRecognizer'i bir kez yukleyip surec omru boyunca yeniden
    kullanir - checkpoint yuklemesi pahali, her cagrida tekrarlanmamali."""
    global _recognizer
    if _recognizer is None:
        _recognizer = CrnnRecognizer(checkpoint_path, charset_path, device=device)
    return _recognizer


def run_hybrid_htr(
    image_path: str,
    checkpoint_path: str,
    charset_path: str,
    device: str = "cpu",
) -> HtrPageResult:
    """Kraken ile segmentasyon + CRNN ile tanima. HtrPageResult.htr_run.backend
    "crnn_v2+kraken_seg" olarak isaretlenir ki hangi transkripsiyonun hangi
    modelden geldigi (dolayisiyla guvenilirligi) belli olsun."""
    seg_result = run_kraken(image_path, model_path=None, device=device, segment_only=True)
    line_groups = group_fragments_into_lines(seg_result.lines)

    recognizer = get_recognizer(checkpoint_path, charset_path, device=device)

    with Image.open(image_path) as page_img:
        page_img = page_img.convert("L")
        recognized_lines: list[Line] = []
        for group in line_groups:
            box = BoundingBox.union([frag.bbox for frag in group])
            crop = page_img.crop((box.x_min, box.y_min, box.x_max, box.y_max))
            if crop.width < 2 or crop.height < 2:
                # Bozuk/dejenere bir segment - bos metinle birakip devam et,
                # tum sayfayi sessizce basarisiz kilma.
                recognized_lines.append(
                    Line(id=group[0].id, text="", confidence=None, polygon=group[0].polygon, bbox=box)
                )
                continue
            text, confidence = recognizer.recognize(crop)
            merged_polygon = [p for frag in group for p in frag.polygon]
            recognized_lines.append(
                Line(
                    id=group[0].id,
                    text=text,
                    confidence=confidence,
                    polygon=merged_polygon,
                    bbox=box,
                )
            )

    htr_run = HtrRun(
        htr_run_id=seg_result.htr_run.htr_run_id,
        backend="crnn_v2+kraken_seg",
        model_name=Path(checkpoint_path).stem,
        model_ref=f"kraken segment + {Path(checkpoint_path).name} (device={device})",
    )

    return HtrPageResult(
        image_path=seg_result.image_path,
        image_width=seg_result.image_width,
        image_height=seg_result.image_height,
        htr_run=htr_run,
        lines=recognized_lines,
    )
