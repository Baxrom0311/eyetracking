import asyncio
import websockets
import threading
import json
import logging
import time
from settings import ANDROID_WS_HOST, ANDROID_WS_PORT, ANDROID_ENABLED

logger = logging.getLogger(__name__)


class Notifier:
    """
    Zone trigger bo'lganda:
    1) TTS orqali ovoz chiqaradi
    2) Android ga WebSocket xabar yuboradi
    3) Log ga yozadi
    """

    def __init__(self, tts_engine):
        self.tts        = tts_engine
        self._clients   = set()
        self._loop      = asyncio.new_event_loop()
        self._server    = None
        self._thread    = None
        self._started   = threading.Event()
        if ANDROID_ENABLED:
            self._start_ws_server()

    # ── Xabar yuborish (asosiy) ───────────────────────────
    def notify(self, zone_result: dict):
        msg   = zone_result.get("message", "")
        name  = zone_result.get("zone_name", "")

        # TTS
        self.tts.speak(msg)

        # Log
        logger.info(f"XABAR: [{name}] {msg}")

        # Android WebSocket
        if ANDROID_ENABLED and self._clients:
            payload = json.dumps({
                "type":      "zone_trigger",
                "zone":      name,
                "message":   msg,
                "timestamp": time.time(),
            })
            asyncio.run_coroutine_threadsafe(
                self._broadcast(payload), self._loop
            )

    # ── WebSocket server ─────────────────────────────────
    def _start_ws_server(self):
        def run():
            asyncio.set_event_loop(self._loop)
            try:
                self._loop.run_until_complete(self._serve())
                self._started.set()
            except Exception as e:
                logger.error(f"WebSocket server start xatosi: {e}")
                self._started.set()
                return
            self._loop.run_forever()

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
        self._started.wait(timeout=2.0)
        logger.info(f"WebSocket server: ws://{ANDROID_WS_HOST}:{ANDROID_WS_PORT}")

    async def _serve(self):
        self._server = await websockets.serve(
            self._handler, ANDROID_WS_HOST, ANDROID_WS_PORT
        )

    async def _handler(self, ws):
        self._clients.add(ws)
        logger.info(f"Android ulandi: {ws.remote_address}")
        try:
            await ws.wait_closed()
        finally:
            self._clients.discard(ws)
            logger.info("Android uzildi.")

    async def _broadcast(self, msg: str):
        dead = set()
        for ws in self._clients:
            try:
                await ws.send(msg)
            except Exception:
                dead.add(ws)
        self._clients -= dead

    async def _shutdown(self):
        dead = list(self._clients)
        self._clients.clear()
        for ws in dead:
            try:
                await ws.close()
            except Exception:
                pass
        if self._server is not None:
            self._server.close()
            try:
                await self._server.wait_closed()
            except Exception as e:
                logger.debug(f"Server wait_closed xatosi: {e}")

    def stop(self):
        if not ANDROID_ENABLED or self._thread is None:
            return
        self._started.wait(timeout=2.0)
        if self._server is None:
            return
        try:
            fut = asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop)
            fut.result(timeout=2.0)
        except Exception as e:
            logger.debug(f"WebSocket shutdown xatosi: {e}")
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=2.0)
