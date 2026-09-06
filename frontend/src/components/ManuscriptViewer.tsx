import type { Citation } from "../api";
import { pageImageUrl } from "../api";
import { useLanguage } from "../i18n/LanguageContext";

interface Props {
  citation: Citation;
}

/**
 * Sayfa gorseli, bboxes ile birebir eslesen bir <svg viewBox> icinde
 * gosterilir. viewBox = gorselin orijinal piksel boyutu oldugu icin
 * <rect> koordinatlari manuel olcekleme gerekmeden dogru yerde kalir.
 */
export function ManuscriptViewer({ citation }: Props) {
  const { t } = useLanguage();

  if (!citation.image_path || !citation.image_width || !citation.image_height) {
    return <p className="viewer-empty">{t.viewerEmpty}</p>;
  }

  const w = citation.image_width;
  const h = citation.image_height;

  return (
    <div className="viewer">
      <svg viewBox={`0 0 ${w} ${h}`} className="viewer-svg" preserveAspectRatio="xMidYMin meet">
        <image href={pageImageUrl(citation.page_id)} width={w} height={h} />
        {citation.bboxes.map((b, i) => (
          <rect
            key={i}
            x={b.x_min}
            y={b.y_min}
            width={b.x_max - b.x_min}
            height={b.y_max - b.y_min}
            className="highlight-box"
          />
        ))}
      </svg>
      <p className="citation-label">{citation.citation_label ?? citation.manuscript_id}</p>
    </div>
  );
}
