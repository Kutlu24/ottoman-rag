"""Kraken CLI'yi subprocess olarak calistiran wrapper.

Kraken'in Python API'si surumler arasinda (5.x -> 6.x refactoru ile
kraken.containers modulune gecis gibi) degisiklige ugradi; CLI arayuzu
daha stabil oldugu icin entegrasyonu CLI uzerinden yapiyoruz:

    kraken -i giris.png cikti.xml -x segment -bl ocr -m model.mlmodel

`-x` PAGE XML serilestirmesini secer (satir bazli polygon + metin + conf).
"""

from __future__ import annotations

import subprocess
import tempfile
import uuid
from pathlib import Path

from ottoman_rag_common.htr import HtrPageResult, HtrRun

from .page_xml import parse_page_xml


class KrakenError(RuntimeError):
    pass


def run_kraken(image_path: str, model_path: str) -> HtrPageResult:
    image = Path(image_path)
    model = Path(model_path)

    if not image.exists():
        raise KrakenError(f"Görüntü bulunamadı: {image}")
    if not model.exists():
        raise KrakenError(f"Model bulunamadı: {model}")

    with tempfile.TemporaryDirectory() as tmpdir:
        output_xml = Path(tmpdir) / f"{image.stem}.xml"

        cmd = [
            "kraken",
            "-i", str(image), str(output_xml),
            "-x",
            "segment", "-bl",
            "ocr", "-m", str(model),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise KrakenError(
                f"kraken çalıştırılırken hata oluştu (exit {result.returncode}):\n{result.stderr}"
            )
        if not output_xml.exists():
            raise KrakenError(f"kraken çıktı üretmedi, stderr:\n{result.stderr}")

        htr_run = HtrRun(
            htr_run_id=str(uuid.uuid4()),
            backend="kraken",
            model_name=model.stem,
            model_ref=model.name,
        )
        return parse_page_xml(str(output_xml), str(image), htr_run)
