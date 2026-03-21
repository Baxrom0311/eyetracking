"""
GazeSpeak Web — FastAPI server.
Ishga tushirish:
    cd web && uvicorn app:app --reload --host 0.0.0.0 --port 8000
"""

import json
import logging
import sys
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from session import GazeSession
except ImportError:
    from web.session import GazeSession

try:
    from tts_engine import TTSEngine
except ImportError:
    from ..tts_engine import TTSEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

app = FastAPI(title="GazeSpeak Web", version="1.0.0")
tts_engine = TTSEngine()

# Static fayllar
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.on_event("shutdown")
async def shutdown_event():
    try:
        tts_engine.stop()
    except Exception:
        pass


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    session = GazeSession()
    logger.info("Yangi WebSocket ulanish.")

    try:
        while True:
            message = await ws.receive()

            # Binary frame (JPEG)
            if "bytes" in message and message["bytes"]:
                result = session.process_frame(message["bytes"])
                await ws.send_json(result)

            # JSON buyruq
            elif "text" in message and message["text"]:
                try:
                    data = json.loads(message["text"])
                except json.JSONDecodeError:
                    await ws.send_json({"error": "JSON parse xatosi"})
                    continue

                cmd = data.get("command", "")

                if cmd == "start_calibration":
                    screen_w = data.get("screen_w", 1920)
                    screen_h = data.get("screen_h", 1080)
                    session.start_calibration(screen_w, screen_h)
                    await ws.send_json({"status": "calibration_started"})

                elif cmd == "set_screen":
                    screen_w = data.get("screen_w", 1920)
                    screen_h = data.get("screen_h", 1080)
                    session.set_screen_size(screen_w, screen_h)
                    await ws.send_json({"status": "screen_updated"})

                elif cmd == "reset_calibration":
                    session.reset_calibration()
                    await ws.send_json({"status": "calibration_reset"})

                elif cmd == "speak_text":
                    text = str(data.get("text", "")).strip()
                    if not text:
                        await ws.send_json({"error": "Gapirtirish uchun matn bo'sh"})
                    else:
                        tts_engine.speak(text)
                        await ws.send_json({"status": "tts_started"})

                elif cmd == "ping":
                    await ws.send_json({"status": "pong"})

                else:
                    await ws.send_json({"error": f"Noma'lum buyruq: {cmd}"})

    except WebSocketDisconnect:
        logger.info("WebSocket uzildi.")
    except Exception as e:
        logger.error("WebSocket xatosi: %s", e)
    finally:
        session.close()
        logger.info("Session yopildi.")
