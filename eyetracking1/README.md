# GazeSpeak

Ko'z bilan AAC muloqot tizimi. Harakat imkoniyati cheklangan odamlar uchun.

## Arxitektura

```
Native Python (kamera + MediaPipe) → Qt Desktop AAC UI
```

- **desktop_app.py** — asosiy bemor interfeysi: Qt desktop UI, kamera/tracker bilan to'g'ridan-to'g'ri ishlaydi
- **face_tracker.py / gaze_mapper.py / calibration.py** — ko'z tracking, mapping va kalibratsiya core qismi
- WebSocket/browser qatlamlari olib tashlangan, gaze koordinata UIga bevosita signal orqali boradi

## O'rnatish

```bash
python3.12 -m venv .venv312
source .venv312/bin/activate
pip install -r requirements.txt
```

`models/face_landmarker.task` fayli kerak (birinchi ishga tushirishda avtomatik yuklanadi).

## Ishga tushirish

```bash
python desktop_app.py
```

Desktop app WebSocket/JSON qatlamisiz ishlaydi, shuning uchun bemor uchun latency pastroq bo'ladi.

## Kalibrasiya

1. Desktop app ichida "Kalibratsiya" tugmasini bosing
2. 9 ta nuqtaga navbatma-navbat qarang (har biri 2 sek)
3. Kalibrasiya avtomatik saqlanadi

## Eslatma

- macOS da kamera ruxsati: System Settings → Privacy & Security → Camera
- TTS default holatda `uz-UZ-MadinaNeural` Uzbek neural voice orqali gapiradi (`edge-tts`)
- Birinchi marta gapirganda internet kerak bo'ladi; tayyor audio `.tts_cache/` ichida saqlanadi va keyingi safar tezroq ijro qilinadi
- Erkak ovozi kerak bo'lsa: `GAZESPEAK_TTS_EDGE_VOICE=uz-UZ-SardorNeural python desktop_app.py`
- Internet bo'lmasa macOS `say` fallback ishlatiladi, lekin uning Uzbek talaffuzi neural voice darajasida aniq emas
