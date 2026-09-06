"""RAG orchestrator: search-server'dan provenance'li chunk getirir, Claude'a
zorunlu tool-use ile yapilandirilmis (hangi pasajdan alintilandigini iceren)
bir cevap urettirir, sonucu tam provenance (bbox + gorsel yolu) ile birlikte
dondurur.
"""

from __future__ import annotations

from anthropic import Anthropic
from ottoman_rag_common.geometry import BoundingBox
from pydantic import BaseModel

from . import store
from .config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL
from .mcp_clients import McpClientManager

_anthropic_client: Anthropic | None = None


def get_anthropic_client() -> Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        if not ANTHROPIC_API_KEY:
            raise RuntimeError(
                "ANTHROPIC_API_KEY tanımlı değil. Proje kökündeki .env dosyasını "
                "kendi metin editörünüzle açıp anahtarı ekleyin."
            )
        _anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
    return _anthropic_client


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


# $/milyon token (input, output) - sadece bu projede kullanilmasi beklenen
# modeller icin; bilinmeyen bir model icin maliyet tahmini yapilmaz.
_PRICING_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-opus-5": (5.00, 25.00),
}


class Usage(BaseModel):
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float | None = None


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    usage: Usage | None = None


_ANSWER_TOOL = {
    "name": "provide_answer",
    "description": (
        "Verilen pasajlara dayanarak araştırmacının sorusuna Türkçe cevap ver. "
        "SADECE pasajlarda yer alan bilgiyi kullan; yeterli bilgi yoksa bunu açıkça "
        "belirt. Cevabının hangi pasaj(lar)a dayandığını mutlaka belirt."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "answer": {"type": "string"},
            "citations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "passage_index": {
                            "type": "integer",
                            "description": "Kullanılan pasajın numarası (aşağıdaki listede 1'den başlar).",
                        },
                        "quote": {
                            "type": "string",
                            "description": "O pasajdan cevabı destekleyen kısa, birebir alıntı.",
                        },
                    },
                    "required": ["passage_index", "quote"],
                },
            },
        },
        "required": ["answer", "citations"],
    },
}


def _build_prompt(question: str, passages: list[dict], language: str) -> str:
    if language == "en":
        lines = [
            "You are an assistant helping with research on Ottoman manuscripts.",
            "The following passages were transcribed via HTR (handwritten text "
            "recognition) from source documents; they may contain garbled "
            "characters from recognition errors. Answer ONLY in English, based "
            "solely on these passages; if they are not sufficient to answer the "
            "question, say so clearly rather than guessing.",
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
        "metinlerdir; tanıma hatalarından kaynaklanan bozuk karakterler içerebilir. "
        "SADECE bu pasajlara dayanarak Türkçe cevap ver; pasajlar soruyu "
        "yanıtlamaya yetmiyorsa bunu açıkça belirt, tahminde bulunma.",
        "",
        "Pasajlar:",
    ]
    for i, p in enumerate(passages, start=1):
        lines.append(f"[{i}] (Kaynak: {p.get('citation_label') or p['manuscript_id']}) {p['text']}")
    lines.append("")
    lines.append(f"Soru: {question}")
    return "\n".join(lines)


async def answer_question(
    mcp_manager: McpClientManager,
    question: str,
    manuscript_id: str | None = None,
    top_k: int = 5,
    language: str = "tr",
) -> AskResponse:
    search_client = mcp_manager.get("search")
    passages: list[dict] = await search_client.call_tool(
        "search",
        {"query": question, "top_k": top_k, "manuscript_id": manuscript_id},
    )

    if not passages:
        no_source_msg = (
            "No indexed source was found for this question."
            if language == "en"
            else "Bu soruyla ilgili dizinlenmiş bir kaynak bulunamadı."
        )
        return AskResponse(answer=no_source_msg, citations=[])

    prompt = _build_prompt(question, passages, language)
    client = get_anthropic_client()
    message = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2048,
        tools=[_ANSWER_TOOL],
        tool_choice={"type": "tool", "name": "provide_answer"},
        messages=[{"role": "user", "content": prompt}],
    )
    tool_use = next(b for b in message.content if b.type == "tool_use")
    payload = tool_use.input

    in_tok = message.usage.input_tokens
    out_tok = message.usage.output_tokens
    pricing = _PRICING_PER_MTOK.get(ANTHROPIC_MODEL)
    cost = (in_tok / 1_000_000 * pricing[0] + out_tok / 1_000_000 * pricing[1]) if pricing else None
    usage = Usage(model=ANTHROPIC_MODEL, input_tokens=in_tok, output_tokens=out_tok, estimated_cost_usd=cost)

    citations: list[Citation] = []
    for c in payload.get("citations", []):
        idx = c.get("passage_index", 0) - 1
        if idx < 0 or idx >= len(passages):
            continue
        p = passages[idx]
        page = store.get_page(p["page_id"])
        citations.append(
            Citation(
                chunk_id=p["chunk_id"],
                manuscript_id=p["manuscript_id"],
                page_id=p["page_id"],
                citation_label=p.get("citation_label"),
                line_ids=p["line_ids"],
                bboxes=[BoundingBox(**b) for b in p["bboxes"]],
                image_path=page.image_path if page else None,
                image_width=page.image_width if page else None,
                image_height=page.image_height if page else None,
                quote=c.get("quote", ""),
            )
        )

    return AskResponse(answer=payload.get("answer", ""), citations=citations, usage=usage)
