import threading
import queue
import logging
import shutil
import subprocess
from settings import TTS_ENABLED, TTS_RATE, TTS_VOLUME

logger = logging.getLogger(__name__)


class TTSEngine:
    """
    Alohida threadda pyttsx3 orqali ovoz chiqaradi.
    Queue bilan — asosiy loop ni to'sib qolmaydi.
    """

    def __init__(self):
        self._q      = queue.Queue()
        self._enabled = TTS_ENABLED
        self._thread = None
        if self._enabled:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            logger.info("TTS engine ishga tushdi.")
        else:
            logger.info("TTS engine o'chirilgan.")

    def speak(self, text: str):
        """Matnni ovoz navbatiga qo'shadi."""
        if not self._enabled:
            return
        self._q.put(text)

    def _run(self):
        engine = None
        use_say = False
        try:
            import pyttsx3

            engine = pyttsx3.init()
            engine.setProperty("rate", TTS_RATE)
            engine.setProperty("volume", TTS_VOLUME)
        except Exception as e:
            if shutil.which("say"):
                use_say = True
                logger.warning(f"pyttsx3 ishlamadi, macOS 'say' fallback ishlatiladi: {e}")
            else:
                logger.error(f"TTS init xatosi: {e}")
                return

        while True:
            try:
                text = self._q.get(timeout=0.5)
                if text is None:
                    break
                if use_say:
                    subprocess.run(["say", text], check=False)
                else:
                    engine.say(text)
                    engine.runAndWait()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"TTS xatosi: {e}")

    def stop(self):
        if not self._enabled:
            return
        self._q.put(None)
        if self._thread is not None:
            self._thread.join(timeout=2.0)
