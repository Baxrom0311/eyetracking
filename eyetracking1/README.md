# GazeSpeak

Ko'z bilan AAC tanlash, kalibrasiya, TTS va yordamchi desktop preview.

## O'rnatish

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` desktop preview va web AAC uchun umumiy paketlarni o'rnatadi.
`models/face_landmarker.task` fayli repo ichida bo'lishi kerak.

## Ishga tushirish

Face tracking preview:

```bash
python test_face.py
```

To'liq ilova:

```bash
python main.py
```

Web AAC paneli:

```bash
cd web
uvicorn app:app --host 127.0.0.1 --port 8000
```

Brauzerda `http://127.0.0.1:8000` ni oching. AAC ishlatish uchun asosiy yo'l shu.

## Tugmalar

- `Q` yoki `ESC`: chiqish
- `C`: qayta kalibrasiya
- `D`: debug landmark overlay
- `M`: cursor control on/off
- `R`: zona dwell timer reset

## Oqim

1. Web panel yoki desktop preview calibration surface bo'yicha 9 nuqtali kalibrasiyani qiladi.
2. Kalibrasiya tugagach gaze AAC tile'lariga yoki desktop preview overlay'ga map qilinadi.
3. Web panel katta tugmalarni dwell orqali tanlaydi va matnni TTS ga yuboradi.
4. Desktop preview default holatda AAC/zone signal rejimida ishlaydi; `M` pointer rejimiga o'tkazadi.

## Eslatma

- macOS'da kamera ruxsati `System Settings -> Privacy & Security -> Camera` ichida terminalingizga berilgan bo'lishi kerak.
- TTS uchun `pyttsx3` bo'lmasa, macOS `say` fallback ishlatiladi.
- Android WebSocket default xavfsiz host: `ws://127.0.0.1:8765`
