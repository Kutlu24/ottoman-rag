"""Kraken CLI'yi subprocess olarak calistiran wrapper.

Kraken'in Python API'si surumler arasinda (5.x -> 6.x refactoru ile
kraken.containers modulune gecis gibi) degisiklige ugradi; CLI arayuzu
daha stabil oldugu icin entegrasyonu CLI uzerinden yapiyoruz:

    kraken -i giris.png cikti.xml -x segment -bl ocr -m model.mlmodel

`-x` PAGE XML serilestirmesini secer (satir bazli polygon + metin + conf).
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from ottoman_rag_common.htr import HtrPageResult, HtrRun

from .page_xml import parse_page_xml


class KrakenError(RuntimeError):
    pass


def _resolve_kraken_executable() -> str:
    """"kraken" komutunu PATH aramasina birakmak yerine, bu surecin kendi
    calistigi Python yorumlayicisiyla (sys.executable) ayni conda ortaminda
    ara. Boylece backend/MCP sunucusu conda activate yapilmadan (ör. tam
    yorumlayici yoluyla) baslatilsa bile kraken.exe bulunur - PATH'te
    "kraken" adiyla eslesen (varsa) baska/yanlis bir ortamin sürümüne
    duşulmez."""
    candidate = Path(sys.executable).parent / "Scripts" / "kraken.exe"  # Windows
    if candidate.exists():
        return str(candidate)
    candidate = Path(sys.executable).parent / "kraken"  # Unix
    if candidate.exists():
        return str(candidate)
    return "kraken"  # son care: PATH aramasi


def run_kraken(image_path: str, model_path: str, device: str = "cpu") -> HtrPageResult:
    """device: kraken'in -d/--device bayragi - "cpu" (varsayilan, her yerde
    calisir), veya gercek bir GPU'su olan bir makinede/uzak sunucuda
    "cuda:0" gibi bir deger. Uzak GPU altyapisi (Google Cloud, universite
    sunucusu vb.) kullanan kurulumlarda bu deger "cuda:0" verilir - bkz.
    mcp-servers/remote-htr-server."""
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
            _resolve_kraken_executable(),
            "-d", device,
            "-i", str(image), str(output_xml),
            "-x",
            "segment", "-bl",
            "ocr", "-m", str(model),
            # PyTorch/kraken'in kendi ic worker havuzlarini (num_workers vb.)
            # tek surece indirir; asil deadlock nedeni asagidaki stdin
            # duzeltmesiydi ama bu da ekstra guvenlik.
            "--num-line-workers", "0",
        ]
        # KRITIK: stdin'i acikca DEVNULL'a baglamak gerekiyor. htr-kraken MCP
        # sunucusu (bu kodun calistigi surec) kendi stdin'ini backend'e
        # baglayan bir pipe (MCP stdio protokolu) uzerinden okuyor; stdin
        # burada belirtilmezse subprocess.run bu PIPE handle'ini oldugu gibi
        # kraken.exe alt surecine miras birakiyor (Windows'ta subprocess,
        # stdin=None oldugunda mevcut stdin handle'ini acikca inherit-edilebilir
        # yapip child'a geciriyor). O pipe'in yazma ucu MCP oturumu boyunca
        # acik kaldigindan hicbir zaman EOF gelmiyor; kraken/torch bunu
        # (multiprocessing/dataloader ic mekanizmalarinda) beklerken tum
        # cagri backend -> MCP -> kraken zincirinde sessizce donuyordu.
        # Dogrudan (MCP disinda) calistirilan cagrilarda stdin normal bir
        # konsol/dosya handle'i oldugundan bu sorun hic gorulmuyordu.
        # PYTHONIOENCODING: kraken.exe de bir Python sureci; stdout'u bize
        # (dosyaya) yonlendirilmis oldugu icin Windows'un varsayilan ANSI
        # kod sayfasini (cp1252 vb.) kullanmaya calisiyor ve kendi ilerleme
        # ciktisindaki '✓' gibi Unicode karakterleri yazamayip cokuyor.
        # UTF-8'e zorlamak bunu onluyor.
        child_env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}

        with open(stderr_path, "w", encoding="utf-8") as stderr_file:
            result = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=stderr_file,
                stderr=subprocess.STDOUT,
                env=child_env,
            )

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
            model_ref=f"{model.name} (device={device})",
        )
        return parse_page_xml(str(output_xml), str(image), htr_run)
