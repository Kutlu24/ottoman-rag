import { useState, type FormEvent } from "react";
import { askQuestion, type AskResponse } from "./api";
import { AnswerPanel } from "./components/AnswerPanel";
import { IngestForm } from "./components/IngestForm";
import "./App.css";

type Tab = "ask" | "ingest";

export default function App() {
  const [tab, setTab] = useState<Tab>("ask");
  const [question, setQuestion] = useState("");
  const [manuscriptId, setManuscriptId] = useState("");
  const [result, setResult] = useState<AskResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await askQuestion(question.trim(), manuscriptId.trim() || undefined);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header>
        <h1>Osmanlıca El Yazması Araştırma Asistanı</h1>
        <p className="subtitle">
          Sorunuzu yazın; cevap, kaynak sayfa görüntüsünde ilgili satırlar
          işaretlenmiş şekilde gösterilir.
        </p>
      </header>

      <nav className="tabs">
        <button
          type="button"
          className={tab === "ask" ? "tab active" : "tab"}
          onClick={() => setTab("ask")}
        >
          Soru Sor
        </button>
        <button
          type="button"
          className={tab === "ingest" ? "tab active" : "tab"}
          onClick={() => setTab("ingest")}
        >
          Yeni Sayfa Ekle
        </button>
      </nav>

      {tab === "ask" ? (
        <>
          <form onSubmit={handleSubmit} className="ask-form">
            <input
              type="text"
              placeholder="Yazma eser ID (opsiyonel, boş bırakılırsa tüm koleksiyonda arar)"
              value={manuscriptId}
              onChange={(e) => setManuscriptId(e.target.value)}
            />
            <textarea
              placeholder="Sorunuzu buraya yazın..."
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              rows={3}
              required
            />
            <button type="submit" disabled={loading}>
              {loading ? "Aranıyor..." : "Sor"}
            </button>
          </form>

          {error && <p className="error">{error}</p>}
          {result && <AnswerPanel result={result} />}
        </>
      ) : (
        <IngestForm />
      )}
    </div>
  );
}
