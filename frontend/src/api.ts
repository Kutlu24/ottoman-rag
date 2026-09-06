export interface BoundingBox {
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
}

export interface Citation {
  chunk_id: string;
  manuscript_id: string;
  page_id: string;
  citation_label: string | null;
  line_ids: string[];
  bboxes: BoundingBox[];
  image_path: string | null;
  image_width: number | null;
  image_height: number | null;
  quote: string;
}

export interface Usage {
  model: string;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number | null;
}

export interface AskResponse {
  answer: string;
  citations: Citation[];
  usage: Usage | null;
}

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export async function askQuestion(
  question: string,
  manuscriptId?: string,
  topK = 5,
): Promise<AskResponse> {
  const res = await fetch(`${API_BASE}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      manuscript_id: manuscriptId || null,
      top_k: topK,
    }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API hatası (${res.status}): ${text}`);
  }
  return res.json();
}

export function pageImageUrl(pageId: string): string {
  return `${API_BASE}/pages/${encodeURIComponent(pageId)}/image`;
}
