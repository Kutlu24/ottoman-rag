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
  language: "tr" | "en" = "tr",
): Promise<AskResponse> {
  const res = await fetch(`${API_BASE}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      manuscript_id: manuscriptId || null,
      top_k: topK,
      language,
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

export interface ManuscriptRef {
  manuscript_id: string;
  title?: string | null;
  repository?: string | null;
  shelfmark?: string | null;
  date?: string | null;
  collection?: string | null;
  notes?: string | null;
}

export interface PageRef {
  page_id: string;
  manuscript_id: string;
  folio_label?: string | null;
  image_path: string;
  image_width?: number | null;
  image_height?: number | null;
}

export interface UploadImageResponse {
  image_path: string;
  image_width: number;
  image_height: number;
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API hatası (${res.status}): ${text}`);
  }
  return res.json();
}

export async function uploadImage(file: File): Promise<UploadImageResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/upload-image`, { method: "POST", body: form });
  return handle<UploadImageResponse>(res);
}

export async function createManuscript(manuscript: ManuscriptRef): Promise<ManuscriptRef> {
  const res = await fetch(`${API_BASE}/manuscripts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(manuscript),
  });
  return handle<ManuscriptRef>(res);
}

export async function createPage(page: PageRef): Promise<PageRef> {
  const res = await fetch(`${API_BASE}/pages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(page),
  });
  return handle<PageRef>(res);
}

export interface IngestResponse {
  chunks_indexed: number;
}

export async function ingestPage(
  manuscript: ManuscriptRef,
  page: PageRef,
  krakenModel?: string,
): Promise<IngestResponse> {
  const res = await fetch(`${API_BASE}/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ manuscript, page, kraken_model: krakenModel || null }),
  });
  return handle<IngestResponse>(res);
}
