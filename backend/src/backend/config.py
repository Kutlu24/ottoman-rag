from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# backend/src/backend/config.py -> parents[3] proje koku
PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
# Haiku 4.5: en ucuz mevcut Claude modeli ($1/$5 per MTok) - bu projenin
# kisa, retrieval ile sinirli prompt'lari icin maliyet/kalite dengesi iyi.
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

METADATA_DB_PATH = Path(
    os.environ.get("METADATA_DB_PATH", str(PROJECT_ROOT / "data" / "metadata.db"))
)

SEARCH_SERVER_DIR = PROJECT_ROOT / "mcp-servers" / "search-server" / "src"
HTR_KRAKEN_DIR = PROJECT_ROOT / "mcp-servers" / "htr-server" / "src"


def _resolve_path(env_value: str, default: Path) -> str:
    """.env'deki goreli yollari, alt MCP sunucu subprocess'lerinin farkli
    cwd'lerine gore degil, her zaman proje kokune gore coz.

    (Bu duzeltmeden once CHROMA_DB_DIR=./data/chroma gibi bir deger,
    search-server subprocess'i mcp-servers/search-server/src cwd'siyle
    baslatildiginda mcp-servers/search-server/src/data/chroma gibi yanlis
    - ve bos - bir klasore cozuluyordu.)
    """
    p = Path(env_value) if env_value else default
    return str(p if p.is_absolute() else (PROJECT_ROOT / p))


CHROMA_DB_DIR = _resolve_path(os.environ.get("CHROMA_DB_DIR", ""), PROJECT_ROOT / "data" / "chroma")
EMBEDDING_MODEL_NAME = os.environ.get("EMBEDDING_MODEL_NAME", "intfloat/multilingual-e5-base")

KRAKEN_MODEL_DIR = _resolve_path(
    os.environ.get("KRAKEN_MODEL_DIR", ""), PROJECT_ROOT / "mcp-servers" / "htr-server" / "models"
)
KRAKEN_DEFAULT_MODEL = os.environ.get("KRAKEN_DEFAULT_MODEL", "")

# Yuklenen sayfa gorselleri. Kalici depolama gerektiren tek "kullanici
# verisi" dizinlerinden biri (digerleri: CHROMA_DB_DIR, METADATA_DB_PATH) -
# HF Spaces gibi ortamlarda /data altindaki kalici bir yola yonlendirilmeli.
RAW_IMAGES_DIR = Path(
    _resolve_path(os.environ.get("RAW_IMAGES_DIR", ""), PROJECT_ROOT / "data" / "raw_images")
)

# Bos birakilirsa (yerel gelistirmede oldugu gibi) Basic Auth devre disi
# kalir; production'da (HF Spaces secrets) mutlaka doldurulmali - aksi
# halde ANTHROPIC_API_KEY gercek para harcayan, herkese acik bir uc nokta
# arkasinda korumasiz kalir.
BASIC_AUTH_USER = os.environ.get("BASIC_AUTH_USER", "")
BASIC_AUTH_PASSWORD = os.environ.get("BASIC_AUTH_PASSWORD", "")
