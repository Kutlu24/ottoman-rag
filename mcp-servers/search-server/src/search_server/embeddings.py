"""Coklu dilli, acik kaynak embedding modeli sarmalayicisi.

intfloat/multilingual-e5-base sorgu ve pasajlar icin farkli onek bekler
(https://huggingface.co/intfloat/multilingual-e5-base) - bu fark burada
soyutlaniyor, cagiran kod sadece is_query bayragini veriyor.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

_MODEL_NAME = os.environ.get("EMBEDDING_MODEL_NAME", "intfloat/multilingual-e5-base")
_model: "SentenceTransformer | None" = None


def get_model() -> "SentenceTransformer":
    # Import burada, fonksiyon icinde: sentence_transformers -> torch'u
    # modul yuklenirken degil, ilk gercek embedding cagrisinda yukler.
    # search-server MCP alt sureci sadece acilirken (henuz hicbir sorgu
    # gelmeden) torch'u belleğe almasin diye - kucuk bellekli ortamlarda
    # (ör. Render'in ucretsiz 512MB'i) baslangicta OOM riskini azaltir.
    from sentence_transformers import SentenceTransformer

    global _model
    if _model is None:
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def embed_texts(texts: list[str], is_query: bool = False) -> list[list[float]]:
    if not texts:
        return []
    prefix = "query: " if is_query else "passage: "
    prefixed = [prefix + t for t in texts]
    vectors = get_model().encode(prefixed, normalize_embeddings=True)
    return vectors.tolist()
