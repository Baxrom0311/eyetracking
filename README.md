# GazeSpeak

Ko'z bilan cursor boshqarish, kalibrasiya, zona dwell trigger, TTS va WebSocket bildirishnomalari.

## O'rnatish

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

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

## Tugmalar

- `Q` yoki `ESC`: chiqish
- `C`: qayta kalibrasiya
- `D`: debug landmark overlay
- `M`: cursor control on/off
- `R`: zona dwell timer reset

## Oqim

1. Agar `calibration.json` mavjud bo'lmasa, ilova 9 nuqtali kalibrasiyadan boshlaydi.
2. Kalibrasiya tugagach gaze mapping cursor'ga ulanadi.
3. Bir zonada 10 soniya ushlab turilsa TTS va WebSocket xabari yuboriladi.
4. 2 soniya harakatsiz qaralsa dwell click ishlaydi.

## Eslatma

- macOS'da kamera ruxsati `System Settings -> Privacy & Security -> Camera` ichida terminalingizga berilgan bo'lishi kerak.
- TTS uchun `pyttsx3` bo'lmasa, macOS `say` fallback ishlatiladi.
- WebSocket server default: `ws://0.0.0.0:8765`
