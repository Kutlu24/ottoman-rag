import { useState, type FormEvent } from "react";
import { createManuscript, createPage, ingestPage, uploadImage } from "../api";
import { useLanguage } from "../i18n/LanguageContext";

const emptyState = {
  manuscriptId: "",
  title: "",
  repository: "",
  shelfmark: "",
  date: "",
  folioLabel: "",
  krakenModel: "",
};

export function IngestForm() {
  const { t } = useLanguage();
  const [form, setForm] = useState(emptyState);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function set<K extends keyof typeof emptyState>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!file || !form.manuscriptId.trim()) return;

    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setStep(t.ingestStepUpload);
      const uploaded = await uploadImage(file);

      const manuscript = {
        manuscript_id: form.manuscriptId.trim(),
        title: form.title.trim() || null,
        repository: form.repository.trim() || null,
        shelfmark: form.shelfmark.trim() || null,
        date: form.date.trim() || null,
      };
      const pageId = `${manuscript.manuscript_id}-${form.folioLabel.trim() || "p1"}`;
      const page = {
        page_id: pageId,
        manuscript_id: manuscript.manuscript_id,
        folio_label: form.folioLabel.trim() || null,
        image_path: uploaded.image_path,
        image_width: uploaded.image_width,
        image_height: uploaded.image_height,
      };

      setStep(t.ingestStepRecord);
      await createManuscript(manuscript);
      await createPage(page);

      setStep(t.ingestStepRun);
      const ingestResult = await ingestPage(manuscript, page, form.krakenModel || undefined);

      setResult(t.ingestSuccess(ingestResult.chunks_indexed, manuscript.manuscript_id));
      setForm(emptyState);
      setFile(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
      setStep("");
    }
  }

  return (
    <form onSubmit={handleSubmit} className="ingest-form">
      <div className="field-row">
        <label>
          {t.ingestManuscriptId}
          <input
            value={form.manuscriptId}
            onChange={(e) => set("manuscriptId", e.target.value)}
            required
          />
        </label>
        <label>
          {t.ingestFolioLabel}
          <input
            value={form.folioLabel}
            onChange={(e) => set("folioLabel", e.target.value)}
            placeholder={t.ingestFolioPlaceholder}
          />
        </label>
      </div>

      <div className="field-row">
        <label>
          {t.ingestTitle}
          <input value={form.title} onChange={(e) => set("title", e.target.value)} />
        </label>
        <label>
          {t.ingestRepository}
          <input value={form.repository} onChange={(e) => set("repository", e.target.value)} />
        </label>
      </div>

      <div className="field-row">
        <label>
          {t.ingestShelfmark}
          <input value={form.shelfmark} onChange={(e) => set("shelfmark", e.target.value)} />
        </label>
        <label>
          {t.ingestDate}
          <input value={form.date} onChange={(e) => set("date", e.target.value)} />
        </label>
      </div>

      <label>
        {t.ingestKrakenModel}
        <input
          value={form.krakenModel}
          onChange={(e) => set("krakenModel", e.target.value)}
          placeholder={t.ingestKrakenModelPlaceholder}
        />
      </label>

      <label>
        {t.ingestImage}
        <input
          type="file"
          accept="image/jpeg,image/png,image/tiff"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          required
        />
      </label>

      <button type="submit" disabled={busy}>
        {busy ? step || t.ingestSubmitBusy : t.ingestSubmit}
      </button>

      {error && <p className="error">{error}</p>}
      {result && <p className="success">{result}</p>}
    </form>
  );
}
