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
- Birinchi marta gapirganda internet kerak bo'ladi; tayyor audio OS cache katalogida saqlanadi va keyingi safar tezroq ijro qilinadi
- Erkak ovozi kerak bo'lsa: `GAZESPEAK_TTS_EDGE_VOICE=uz-UZ-SardorNeural python desktop_app.py`
- Internet bo'lmasa macOS `say` fallback ishlatiladi, lekin uning Uzbek talaffuzi neural voice darajasida aniq emas

## Production build

Installer build uchun qo'shimcha toolchain:

```bash
pip install -r requirements.txt -r requirements-build.txt
```

Yig'ilgan release artifact `target` kompyuterda `Python`, `pip`, `venv`, `Qt`, `MediaPipe` alohida o'rnatilishini talab qilmaydi. Bularning hammasi packaged app ichiga qo'shiladi.

### macOS

```bash
python packaging/build_release.py --clean --target macos
```

Natija:

- `release/GazeSpeak-0.4.0-macOS.dmg`

Optional signing/notarization:

- `APPLE_SIGN_IDENTITY` - `codesign` identity
- `APPLE_NOTARY_PROFILE` - `xcrun notarytool` keychain profile

### Windows

Windows native runner yoki Windows mashina kerak:

```powershell
python packaging/build_release.py --clean --target windows
```

Natija:

- `release/GazeSpeak-0.4.0-Windows-Setup.exe`

Windows installer `Inno Setup 6` bilan yig'iladi. Agar `ISCC.exe` standart joyda bo'lmasa, `ISCC_PATH` env orqali ko'rsating.
`setup.exe` ichida packaged app, Python runtime, Qt kutubxonalari va kerakli Windows runtime fayllari birga bo'ladi.
Build script `ISCC.exe` topmasa Windowsda avval `winget`, keyin `choco` orqali `Inno Setup`ni avtomatik o'rnatishga ham urinadi.

### Smoke check

Packaged app yoki source runtime minimal tekshiruv:

```bash
python desktop_app.py --self-check
```

Bu:

- importlar
- bundled model path
- runtime data/cache path
- Qt startup

ni tekshiradi. `GAZESPEAK_SELF_CHECK_TRACKER=1` bo'lsa, `FaceTracker` init ham `strict` rejimda tekshiriladi.

## CI build

Cross-platform artifact build workflow repo root ichida:

- `eyetracking/.github/workflows/build-release.yml`

Workflow:

- `macos-latest` da `.dmg`
- `windows-latest` da `setup.exe`
- builddan keyin `--self-check`
- artifact upload

Release uchun `v*` tag push qiling yoki `workflow_dispatch` ishlating.

## Runtime storage

Production build endi repo ichiga yozmaydi:

- calibration file - OS user data katalogida
- TTS cache - OS cache katalogida
- model - avval bundled model, bo'lmasa user data ichiga yuklanadi

Sandbox/headless muhitda fallback sifatida lokal `.runtime/` ishlatiladi.

Automatik yaratiladigan papkalar:

- macOS: `~/Library/Application Support/GazeSpeak Desktop`
- macOS cache: `~/Library/Caches/GazeSpeak Desktop`
- Windows: `%LOCALAPPDATA%\GazeSpeak Desktop`
- Windows cache: `%LOCALAPPDATA%\GazeSpeak Desktop\Cache`

App birinchi ishga tushganda shu papkalarni o'zi yaratadi va calibration, cache, model kabi fayllarni shu yerga saqlaydi.

## Muhim production eslatma

Unsigned buildlar:

- macOS da Gatekeeper warning berishi mumkin
- Windows da SmartScreen warning berishi mumkin

Shuning uchun haqiqiy release uchun:

- macOS: sign + notarize
- Windows: code signing certificate bilan `setup.exe` ni imzolash

## Rasmiy hujjatlar

- PyInstaller spec files: https://pyinstaller.org/en/stable/spec-files.html
- PyInstaller runtime paths: https://pyinstaller.org/en/stable/runtime-information.html
- Qt for Python deployment/PyInstaller: https://doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html
- Inno Setup help: https://jrsoftware.org/ishelp/contents.htm
