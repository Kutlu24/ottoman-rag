"""Kutlu24'un kendi egittigi Osmanlica CRNN (CNN+LSTM) satir-tanima modeli.

Mimari, on-isleme ve CharacterSet mantigi, modelin egitildigi Google Colab
notebook'undaki (Ottoman_OCR_Training.ipynb, "Osmanlica OCR - Resume
Training" hucresi) tanimlarla BIREBIR ayni olmali - checkpoint'in
state_dict'i bu tam mimariye gore kaydedildi, ufak bir fark (ör. LSTM
input_size veya conv katman sirasi) checkpoint'in hic yuklenmemesine ya da
sessizce yanlis agirliklarla calismasina yol acar.

Bu model SADECE tanima yapar: onceden kirpilmis, tek satirlik bir goruntu
alir, metne cevirir. Sayfa segmentasyonu (bir sayfada satirlarin nerede
oldugunu bulma) yapamaz - bkz. server.py'deki hibrit akis (Kraken
segmentasyon + bu model tanima)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image

IMAGE_HEIGHT = 64
IMAGE_WIDTH = 800


class CRNN_v2(nn.Module):
    def __init__(self, num_classes: int):
        super().__init__()
        self.cnn = nn.Sequential(
            nn.Conv2d(1, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(True), nn.MaxPool2d(2, 2),
            nn.Conv2d(64, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(True), nn.MaxPool2d(2, 2),
            nn.Conv2d(128, 256, 3, padding=1), nn.BatchNorm2d(256), nn.ReLU(True),
            nn.Conv2d(256, 256, 3, padding=1), nn.BatchNorm2d(256), nn.ReLU(True), nn.MaxPool2d((2, 1)),
            nn.Conv2d(256, 512, 3, padding=1), nn.BatchNorm2d(512), nn.ReLU(True),
            nn.Conv2d(512, 512, 3, padding=1), nn.BatchNorm2d(512), nn.ReLU(True), nn.MaxPool2d((2, 1)),
        )
        # 64 yukseklik, 4x MaxPool2d(2,...) ile /16 -> 4 kalan yukseklik;
        # forward'da kanal*yukseklik tek bir zaman-adimi ozelligine
        # (512*4=2048) birlestiriliyor, sadece kanal sayisina degil.
        self.rnn = nn.LSTM(512 * 4, 256, num_layers=2, batch_first=True, bidirectional=True, dropout=0.3)
        self.fc = nn.Linear(512, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        conv = self.cnn(x)
        b, c, h, w = conv.size()
        conv = conv.permute(0, 3, 1, 2).reshape(b, w, c * h)
        rnn_out, _ = self.rnn(conv)
        return F.log_softmax(self.fc(rnn_out), dim=2)


class CharacterSet:
    def __init__(self, char_to_idx: dict[str, int]):
        self.char_to_idx = char_to_idx
        self.idx_to_char = {v: k for k, v in char_to_idx.items()}
        self.num_classes = len(char_to_idx)

    @classmethod
    def from_json(cls, path: str | Path) -> "CharacterSet":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls(data["char_to_idx"])

    def decode(self, indices: list[int]) -> str:
        """CTC greedy decode: blank'i (0) ve ardisik tekrarlari at."""
        res: list[str] = []
        prev: int | None = None
        for idx in indices:
            if idx != 0 and idx != prev:
                res.append(self.idx_to_char.get(idx, ""))
            prev = idx
        return "".join(res)


def preprocess_line_image(img: Image.Image) -> torch.Tensor:
    """Egitimdeki OttomanDataset.__getitem__ ile birebir ayni on-isleme:
    gri tonlama, en-boy oranini koruyarak yeniden boyutlandirma, SAGA
    yaslanmis (soldan) beyaz dolgu - Osmanlica'nin sagdan-sola yazim
    yonune uygun. Donen tensor: [1, IMAGE_HEIGHT, IMAGE_WIDTH] (batch
    boyutu YOK, cagiran taraf ekler)."""
    img = img.convert("L")
    w, h = img.size
    aspect = w / h
    new_h = IMAGE_HEIGHT
    new_w = min(int(new_h * aspect), IMAGE_WIDTH)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    padded = Image.new("L", (IMAGE_WIDTH, IMAGE_HEIGHT), 255)
    padded.paste(img, (IMAGE_WIDTH - new_w, 0))
    tensor = torch.FloatTensor(np.array(padded)) / 255.0
    return tensor.unsqueeze(0)


class CrnnRecognizer:
    """Checkpoint + charset'i bir kez yukleyip tekrar tekrar satir tanima
    yapmak icin. Cagiran taraf tek bir ornek olusturup saklamali (model
    yuklemesi pahali)."""

    def __init__(self, checkpoint_path: str | Path, charset_path: str | Path, device: str = "cpu"):
        self.device = torch.device(device)
        self.charset = CharacterSet.from_json(charset_path)
        self.model = CRNN_v2(self.charset.num_classes).to(self.device)
        state_dict = torch.load(checkpoint_path, map_location=self.device)
        self.model.load_state_dict(state_dict)
        self.model.eval()

    @torch.no_grad()
    def recognize(self, img: Image.Image) -> tuple[str, float]:
        """Bir satir goruntusunu tanir. Donen: (metin, ortalama_guven).
        Guven, her zaman-adiminda secilen karakterin softmax olasiliginin
        (blank harici adimlar uzerinden) ortalamasi - kaba ama kullanisli
        bir gosterge."""
        tensor = preprocess_line_image(img).unsqueeze(0).to(self.device)  # [1, 1, H, W]
        log_probs = self.model(tensor)  # [1, T, num_classes]
        probs = log_probs.exp()[0]  # [T, num_classes]
        confs, indices = probs.max(dim=1)  # [T], [T]
        indices_list = indices.tolist()
        text = self.charset.decode(indices_list)

        kept_confs = [c for c, idx in zip(confs.tolist(), indices_list) if idx != 0]
        confidence = float(sum(kept_confs) / len(kept_confs)) if kept_confs else 0.0
        return text, confidence
