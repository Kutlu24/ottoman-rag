import { useState, type FormEvent } from "react";
import { askQuestion, type AskResponse } from "./api";
import { AnswerPanel } from "./components/AnswerPanel";
import { IngestForm } from "./components/IngestForm";
import { useLanguage } from "./i18n/LanguageContext";
import "./App.css";

type Tab = "ask" | "ingest";

export default function App() {
  const { lang, setLang, t } = useLanguage();
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
      const res = await askQuestion(question.trim(), manuscriptId.trim() || undefined, 5, lang);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <div className="lang-switch">
        <button
          type="button"
          className={lang === "tr" ? "lang-btn active" : "lang-btn"}
          onClick={() => setLang("tr")}
        >
          TR
        </button>
        <button
          type="button"
          className={lang === "en" ? "lang-btn active" : "lang-btn"}
          onClick={() => setLang("en")}
        >
          EN
        </button>
      </div>

      <header>
        <h1>{t.appTitle}</h1>
        <p className="subtitle">{t.appSubtitle}</p>
      </header>

      <nav className="tabs">
        <button
          type="button"
          className={tab === "ask" ? "tab active" : "tab"}
          onClick={() => setTab("ask")}
        >
          {t.tabAsk}
        </button>
        <button
          type="button"
          className={tab === "ingest" ? "tab active" : "tab"}
          onClick={() => setTab("ingest")}
        >
          {t.tabIngest}
        </button>
      </nav>

      {tab === "ask" ? (
        <>
          <form onSubmit={handleSubmit} className="ask-form">
            <input
              type="text"
              placeholder={t.manuscriptIdPlaceholder}
              value={manuscriptId}
              onChange={(e) => setManuscriptId(e.target.value)}
            />
            <textarea
              placeholder={t.questionPlaceholder}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              rows={3}
              required
            />
            <button type="submit" disabled={loading}>
              {loading ? t.askButtonBusy : t.askButton}
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
