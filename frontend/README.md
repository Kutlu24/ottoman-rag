# frontend

Araştırmacının soru sorduğu, cevabı ve kaynak sayfa görüntüsü üzerinde
ilgili satırların (`bboxes`) highlight edildiği React arayüzü.

## Kurulum ve çalıştırma

```
npm install
npm run dev
```

Varsayılan olarak `backend`'in `http://localhost:8000`'de çalıştığını
varsayar (`VITE_API_BASE` ile değiştirilebilir, bkz. `.env.example`).
Backend'i ayrıca çalıştırmanız gerekir (bkz. `../backend/README.md`).

## Nasıl çalışır

- `src/api.ts` — backend'in `/ask` ve `/pages/{id}/image` uç noktalarına
  tip güvenli fetch sarmalayıcıları.
- `src/components/ManuscriptViewer.tsx` — sayfa görüntüsünü bir `<svg>`
  içinde `viewBox`'ı görüntünün orijinal piksel boyutuna eşitleyerek
  gösterir; `bboxes` doğrudan bu koordinat uzayında `<rect>` olarak çizilir.
  Bu sayede tarayıcı görüntüyü ne kadar küçültüp büyütürse büyütsün,
  highlight kutuları otomatik olarak doğru yerde kalır (manuel ölçekleme
  hesaplaması gerekmez).
- `src/components/AnswerPanel.tsx` — cevabı, her alıntı için bir
  `ManuscriptViewer` + destekleyici alıntı metnini, ve token/maliyet
  bilgisini gösterir.
