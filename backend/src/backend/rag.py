"""RAG orchestrator: search-server'dan provenance'li chunk getirir, yerel
Qwen2.5 modeline (Ollama) duz metin + [1] [2] tarzi atif isaretleriyle bir
cevap urettirir, sonucu tam provenance (bbox + gorsel yolu) ile birlikte
dondurur.

Neden zorunlu tool-use (yapilandirilmis JSON) degil de duz metin + [N]
regex'i: Claude'un zorunlu tool-use'u (bkz. eski git gecmisi) yapilandirilmis
bir JSON semasi (answer + citations dizisi) urettiriyordu - bu, kucuk yerel
modellerde gercek testte cok tutarsizdi. qwen2.5:7b-instruct'ta 3 denemeden
sadece 1'i dogru semayi tutturdu (digerleri yanlis/eksik alan adlari
uydurdu); qwen2.5:14b-instruct'ta durum DAHA KOTUYDU (3/3 yanlis, ustune
33-105 saniye gecikme - buyuk model kucuk bir hiz/dogruluk kazanci saglamadi,
tam tersi). Ayni modele duz metin + metin icinde [1] [2] seklinde atif
istendiginde ise 3/3 dogru formatta, 5-6 saniyede cevap geldi - kucuk
modeller icin serbest metin uretimi, siki bir JSON semasina uymaktan
olculebilir sekilde daha guvenilir.
"""

from __future__ import annotations

import re

import httpx
from openai import OpenAI
from ottoman_rag_common.geometry import BoundingBox
from pydantic import BaseModel

from . import store
from .config import OLLAMA_BASE_URL, OLLAMA_MODEL

_ollama_client: OpenAI | None = None


def get_ollama_client() -> OpenAI:
    # Ollama'nin OpenAI-uyumlu ucnoktasi - "api_key" SDK'nin constructor'i
    # icin zorunlu ama Ollama tarafindan hic kontrol edilmiyor (Tailscale-
    # only yerel bir servise auth gerekmiyor).
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OpenAI(api_key="ollama", base_url=f"{OLLAMA_BASE_URL.rstrip('/')}/v1")
    return _ollama_client


class Citation(BaseModel):
    chunk_id: str
    manuscript_id: str
    page_id: str
    citation_label: str | None = None
    line_ids: list[str]
    bboxes: list[BoundingBox]
    image_path: str | None = None
    image_width: int | None = None
    image_height: int | None = None
    quote: str


class Usage(BaseModel):
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float | None = None  # Yerel model - her zaman None (para maliyeti yok)


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    usage: Usage | None = None


# Cevabin sonundaki [1], [1, 3] gibi atif isaretlerini yakalar - virgul/bosluk
# ile ayrilmis birden fazla numarayi tek eslesmede destekler.
_CITATION_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")

_MAX_QUOTE_CHARS = 240


def _build_prompt(question: str, passages: list[dict], language: str) -> str:
    if language == "en":
        lines = [
            "You are an assistant helping with research on Ottoman manuscripts.",
            "The following passages were transcribed via HTR (handwritten text "
            "recognition) from source documents; HTR on historical Ottoman script "
            "is inherently noisy (misplaced dots/diacritics, dropped letters), so "
            "expect partial legibility rather than a clean transcription. Answer "
            "ONLY in English, based solely on these passages. Give your best-effort "
            "reading even when the text is only partially legible: identify "
            "recognizable words/phrases and what they suggest about the document's "
            "subject, and explicitly flag which parts are uncertain or illegible "
            "(e.g. \"appears to concern X, though Y is unclear due to HTR noise\"). "
            "Never invent specific facts, names, dates, or numbers that are not "
            "actually present in the passages -- only refuse to answer if the "
            "passages are truly illegible or genuinely unrelated to the question, "
            "not merely imperfect.",
            "After every sentence, mark which passage(s) it's based on using "
            "bracket notation like [1] or [2] right after that sentence - do not "
            "use any other format (no JSON, no headings), just plain prose with "
            "these inline citation marks.",
            "",
            "Passages:",
        ]
        for i, p in enumerate(passages, start=1):
            lines.append(f"[{i}] (Source: {p.get('citation_label') or p['manuscript_id']}) {p['text']}")
        lines.append("")
        lines.append(f"Question: {question}")
        return "\n".join(lines)

    lines = [
        "Sen Osmanlıca el yazması araştırmalarına yardımcı olan bir asistansın.",
        "Aşağıdaki pasajlar HTR (el yazması tanıma) ile transkribe edilmiş kaynak "
        "metinlerdir; tarihi Osmanlıca metinlerde HTR doğası gereği gürültülüdür "
        "(yanlış yerleşmiş nokta/harekeler, düşen harfler) - tam temiz bir "
        "transkripsiyon değil, kısmi okunabilirlik bekle. SADECE bu pasajlara "
        "dayanarak Türkçe cevap ver. Metin kısmen okunabilir olsa bile elinden "
        "gelen en iyi okumayı yap: tanıyabildiğin kelime/ifadeleri ve bunların "
        "belgenin konusu hakkında neyi düşündürdüğünü belirt, hangi kısımların "
        "belirsiz/okunaksız olduğunu açıkça işaretle (ör. \"X hakkında görünüyor, "
        "ancak Y kısmı HTR gürültüsü nedeniyle net değil\"). Pasajlarda gerçekten "
        "yer almayan belirli olgular, isimler, tarihler veya sayılar UYDURMA - "
        "sadece pasajlar gerçekten okunaksız veya soruyla tamamen alakasızsa "
        "cevap vermeyi reddet, sırf kusurlu diye değil.",
        "Her cümlenin hangi pasaja dayandığını, cümlenin hemen ardından [1] veya "
        "[2] gibi köşeli parantez içinde belirt - başka hiçbir format kullanma "
        "(JSON yok, başlık yok), sadece bu atıf işaretleriyle düz metin cevap "
        "ver.",
        "",
        "Pasajlar:",
    ]
    for i, p in enumerate(passages, start=1):
        lines.append(f"[{i}] (Kaynak: {p.get('citation_label') or p['manuscript_id']}) {p['text']}")
    lines.append("")
    lines.append(f"Soru: {question}")
    return "\n".join(lines)


def _make_citation(passages: list[dict], idx: int) -> Citation | None:
    if idx < 0 or idx >= len(passages):
        return None
    p = passages[idx]
    page = store.get_page(p["page_id"])
    text = p["text"]
    quote = text if len(text) <= _MAX_QUOTE_CHARS else text[:_MAX_QUOTE_CHARS].rstrip() + "…"
    return Citation(
        chunk_id=p["chunk_id"],
        manuscript_id=p["manuscript_id"],
        page_id=p["page_id"],
        citation_label=p.get("citation_label"),
        line_ids=p["line_ids"],
        bboxes=[BoundingBox(**b) for b in p["bboxes"]],
        image_path=page.image_path if page else None,
        image_width=page.image_width if page else None,
        image_height=page.image_height if page else None,
        # Modelin secip alintiladigi kisa bir cumle degil, pasajin kendi
        # metni (kisaltilmis) - kucuk yerel modelden birebir dogru bir
        # alinti istemek de guvenilmezdi; bu haliyle asla uydurma olamaz,
        # sadece gercek kaynagin kendisi.
        quote=quote,
    )


async def answer_question(
    search_http_client: httpx.AsyncClient,
    question: str,
    manuscript_id: str | None = None,
    top_k: int = 5,
    language: str = "tr",
) -> AskResponse:
    resp = await search_http_client.post(
        "/search", json={"query": question, "top_k": top_k, "manuscript_id": manuscript_id}
    )
    resp.raise_for_status()
    passages: list[dict] = resp.json()

    if not passages:
        no_source_msg = (
            "No indexed source was found for this question."
            if language == "en"
            else "Bu soruyla ilgili dizinlenmiş bir kaynak bulunamadı."
        )
        return AskResponse(answer=no_source_msg, citations=[])

    prompt = _build_prompt(question, passages, language)
    client = get_ollama_client()
    completion = client.chat.completions.create(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    answer = (completion.choices[0].message.content or "").strip()

    usage_obj = completion.usage
    usage = Usage(
        model=OLLAMA_MODEL,
        input_tokens=usage_obj.prompt_tokens if usage_obj else 0,
        output_tokens=usage_obj.completion_tokens if usage_obj else 0,
    )

    # Cevap metninde gecen her benzersiz [N] (veya [N, M]) isaretinden pasaj
    # numaralarini cikar, ilk gecis sirasina gore benzersizlestir.
    seen: set[int] = set()
    ordered_indices: list[int] = []
    for match in _CITATION_RE.finditer(answer):
        for num_str in match.group(1).split(","):
            n = int(num_str.strip()) - 1
            if n not in seen:
                seen.add(n)
                ordered_indices.append(n)

    citations = [c for idx in ordered_indices if (c := _make_citation(passages, idx)) is not None]

    return AskResponse(answer=answer, citations=citations, usage=usage)
