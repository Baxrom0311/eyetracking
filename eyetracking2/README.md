# WebGazer Variants

Bu papkada WebGazer.js asosidagi 2 ta alohida web-demo bor:

- `v1-basic`: tez sinov uchun oddiy variant
- `v2-lab`: calibration + validation + export bilan kuchliroq variant

## Ishga tushirish

Kamera ishlashi uchun sahifani `localhost` orqali oching:

```bash
cd /Users/baxrom/ish_full/med/eyetracking/eyetracking2
python3 -m http.server 8080
```

Keyin brauzerda oching:

```text
http://localhost:8080
```

## Eslatma

- Bu variantlar `WebGazer.js`ni CDN orqali yuklaydi.
- Browser xavfsizligi sababli web-versiya tizim cursorini native usulda boshqara olmaydi.
- Aniqlik yorug'lik, kamera sifati, ekran masofasi va boshni qimirlatmaslikka kuchli bog'liq.
- Agar tracking g'alati bo'lsa, `Reset` yoki `Recalibrate` qiling.

## Foydalanilgan manbalar

- WebGazer README: https://github.com/brownhci/WebGazer
- WebGazer API Wiki: https://github.com/brownhci/WebGazer/wiki/Top-Level-API
- jsPsych WebGazer notes: https://www.jspsych.org/v8/overview/eye-tracking/
