import { useState, type FormEvent } from "react";
import { createManuscript, createPage, ingestPage, uploadImage } from "../api";

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
      setStep("Görüntü yükleniyor...");
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

      setStep("Yazma/sayfa kaydı oluşturuluyor...");
      await createManuscript(manuscript);
      await createPage(page);

      setStep("Kraken ile HTR çalıştırılıyor ve indeksleniyor (bu birkaç dakika sürebilir)...");
      const ingestResult = await ingestPage(manuscript, page, form.krakenModel || undefined);

      setResult(`Tamamlandı: ${ingestResult.chunks_indexed} chunk indekslendi. Yazma ID: ${manuscript.manuscript_id}`);
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
          Yazma eser ID *
          <input
            value={form.manuscriptId}
            onChange={(e) => set("manuscriptId", e.target.value)}
            required
          />
        </label>
        <label>
          Folio / sayfa etiketi
          <input
            value={form.folioLabel}
            onChange={(e) => set("folioLabel", e.target.value)}
            placeholder="ör. 12r"
          />
        </label>
      </div>

      <div className="field-row">
        <label>
          Başlık
          <input value={form.title} onChange={(e) => set("title", e.target.value)} />
        </label>
        <label>
          Kütüphane / repository
          <input value={form.repository} onChange={(e) => set("repository", e.target.value)} />
        </label>
      </div>

      <div className="field-row">
        <label>
          Shelfmark
          <input value={form.shelfmark} onChange={(e) => set("shelfmark", e.target.value)} />
        </label>
        <label>
          Tarih
          <input value={form.date} onChange={(e) => set("date", e.target.value)} />
        </label>
      </div>

      <label>
        Kraken model dosyası (boş bırakılırsa varsayılan kullanılır)
        <input
          value={form.krakenModel}
          onChange={(e) => set("krakenModel", e.target.value)}
          placeholder="ör. ottoman_best.mlmodel"
        />
      </label>

      <label>
        Sayfa görüntüsü *
        <input
          type="file"
          accept="image/jpeg,image/png,image/tiff"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          required
        />
      </label>

      <button type="submit" disabled={busy}>
        {busy ? step || "İşleniyor..." : "Yükle ve İndeksle"}
      </button>

      {error && <p className="error">{error}</p>}
      {result && <p className="success">{result}</p>}
    </form>
  );
}
