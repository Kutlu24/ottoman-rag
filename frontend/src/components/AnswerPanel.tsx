import type { AskResponse } from "../api";
import { ManuscriptViewer } from "./ManuscriptViewer";

export function AnswerPanel({ result }: { result: AskResponse }) {
  return (
    <div className="answer-panel">
      <h2>Cevap</h2>
      <p className="answer-text">{result.answer}</p>

      {result.citations.length > 0 && (
        <>
          <h3>Kaynaklar</h3>
          <div className="citations">
            {result.citations.map((c) => (
              <div className="citation-card" key={c.chunk_id}>
                <ManuscriptViewer citation={c} />
                <blockquote>{c.quote}</blockquote>
              </div>
            ))}
          </div>
        </>
      )}

      {result.usage && (
        <p className="usage-note">
          {result.usage.model} · {result.usage.input_tokens + result.usage.output_tokens} token
          {result.usage.estimated_cost_usd != null &&
            ` · ~$${result.usage.estimated_cost_usd.toFixed(4)}`}
        </p>
      )}
    </div>
  );
}
