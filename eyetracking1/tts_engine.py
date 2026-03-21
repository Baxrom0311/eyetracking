import threading
import queue
import logging
import shutil
import subprocess
import re
from settings import TTS_ENABLED, TTS_RATE, TTS_VOLUME, TTS_LANGUAGE

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
        self._say_voice = None
        self._say_available = shutil.which("say") is not None
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
        text = (text or "").strip()
        if not text:
            return
        self._q.put(text)

    def _normalize_uzbek_text(self, text: str) -> str:
        text = text.strip()
        if not text:
            return text

        text = (
            text.replace("’", "'")
            .replace("`", "'")
            .replace("ʻ", "'")
            .replace("ʼ", "'")
        )

        word_replacements = {
            "yo'q": "yok",
            "to'xta": "tohta",
            "ko'proq": "koprok",
            "xohlayman": "hohlayman",
            "so'z": "soz",
            "so'zlar": "sozlar",
            "o'g'il": "ogil",
            "g'": "g",
            "o'": "o",
        }

        normalized = text
        for src, dst in word_replacements.items():
            normalized = re.sub(src, dst, normalized, flags=re.IGNORECASE)

        normalized = re.sub(r"\bsh\b", "sh", normalized, flags=re.IGNORECASE)
        normalized = normalized.replace("Sh", "Ş").replace("sh", "ş")
        normalized = normalized.replace("Ch", "Ç").replace("ch", "ç")
        normalized = normalized.replace("G'", "G").replace("g'", "g")
        normalized = normalized.replace("O'", "O").replace("o'", "o")
        normalized = normalized.replace("X", "H").replace("x", "h")
        normalized = normalized.replace("Q", "K").replace("q", "k")
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def _prepare_text(self, text: str) -> str:
        if TTS_LANGUAGE == "uz":
            return self._normalize_uzbek_text(text)
        return text

    def _pick_say_voice(self) -> str | None:
        if not self._say_available:
            return None
        try:
            output = subprocess.check_output(["say", "-v", "?"], text=True)
        except Exception as e:
            logger.warning("say voice ro'yxatini olishda xato: %s", e)
            return None

        lines = output.splitlines()
        preferred = [
            ("Yelda", "tr_TR"),
            ("Aru", "kk_KZ"),
            ("Milena", "ru_RU"),
        ]

        for voice_name, locale in preferred:
            for line in lines:
                if line.startswith(voice_name) and locale in line:
                    return voice_name
        return None

    def _configure_engine_voice(self, engine):
        try:
            voices = engine.getProperty("voices") or []
        except Exception:
            return

        preferred_tokens = []
        if TTS_LANGUAGE == "uz":
            preferred_tokens = ["turkish", "tr_", "kazakh", "kk_", "russian", "ru_"]

        for voice in voices:
            blob = " ".join(
                str(part).lower()
                for part in [
                    getattr(voice, "id", ""),
                    getattr(voice, "name", ""),
                    getattr(voice, "languages", ""),
                ]
            )
            if any(token in blob for token in preferred_tokens):
                try:
                    engine.setProperty("voice", voice.id)
                    logger.info("TTS voice tanlandi: %s", getattr(voice, "name", voice.id))
                    return
                except Exception:
                    continue

    def _run(self):
        engine = None
        use_say = False
        try:
            if self._say_available:
                use_say = True
                self._say_voice = self._pick_say_voice()
                if self._say_voice:
                    logger.info("TTS say voice tanlandi: %s", self._say_voice)
                else:
                    logger.info("TTS say default voice ishlatiladi.")
            else:
                import pyttsx3

                engine = pyttsx3.init()
                engine.setProperty("rate", TTS_RATE)
                engine.setProperty("volume", TTS_VOLUME)
                self._configure_engine_voice(engine)
        except Exception as e:
            logger.error(f"TTS init xatosi: {e}")
            return

        while True:
            try:
                text = self._q.get(timeout=0.5)
                if text is None:
                    break
                prepared_text = self._prepare_text(text)
                if use_say:
                    cmd = ["say", "-r", str(TTS_RATE)]
                    if self._say_voice:
                        cmd.extend(["-v", self._say_voice])
                    cmd.append(prepared_text)
                    subprocess.run(cmd, check=False)
                else:
                    engine.say(prepared_text)
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
