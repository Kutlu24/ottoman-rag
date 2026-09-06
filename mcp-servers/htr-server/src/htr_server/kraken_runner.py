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
        stderr_path = Path(tmpdir) / "stderr.log"

        cmd = [
            "kraken",
            "-i", str(image), str(output_xml),
            "-x",
            "segment", "-bl",
            "ocr", "-m", str(model),
            # --num-line-workers 0: satir cikarma isini multiprocessing worker
            # process'lerine degil, ana process icinde yapar. Ic ice subprocess
            # zincirlerinde (backend -> MCP server -> kraken) worker'larin
            # stdout/stderr pipe handle'ini acik tutup ana process cikinca bile
            # kapatmamasi, PIPE ile yakalanan cikti asla EOF almadigi icin
            # subprocess.run'in sonsuza kadar beklemesine (deadlock) yol
            # aciyordu. Ayni nedenle cikti PIPE yerine dosyaya yazdiriliyor.
            "--num-line-workers", "0",
        ]
        with open(stderr_path, "w", encoding="utf-8") as stderr_file:
            result = subprocess.run(cmd, stdout=stderr_file, stderr=subprocess.STDOUT)

        stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace")

        if result.returncode != 0:
            raise KrakenError(
                f"kraken çalıştırılırken hata oluştu (exit {result.returncode}):\n{stderr_text}"
            )
        if not output_xml.exists():
            raise KrakenError(f"kraken çıktı üretmedi, log:\n{stderr_text}")

        htr_run = HtrRun(
            htr_run_id=str(uuid.uuid4()),
            backend="kraken",
            model_name=model.stem,
            model_ref=model.name,
        )
        return parse_page_xml(str(output_xml), str(image), htr_run)
