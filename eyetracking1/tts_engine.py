import asyncio
import hashlib
import logging
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from settings import (
    TTS_CACHE_DIR,
    TTS_EDGE_RATE,
    TTS_EDGE_VOICE,
    TTS_EDGE_VOLUME,
    TTS_ENABLED,
    TTS_LANGUAGE,
    TTS_PROVIDER,
    TTS_RATE,
    TTS_VOLUME,
)

logger = logging.getLogger(__name__)


class TTSEngine:
    """
    Alohida threadda ovoz chiqaradi.
    Uzbek uchun Edge neural TTS ishlatiladi, system voice esa fallback.
    """

    def __init__(self):
        self._q = queue.Queue()
        self._enabled = TTS_ENABLED
        self._thread = None
        self._provider = TTS_PROVIDER if TTS_PROVIDER in {"edge", "auto", "system"} else "edge"
        self._say_voice = None
        self._say_voice_checked = False
        self._say_available = shutil.which("say") is not None
        self._pyttsx3_engine = None
        self._audio_player = self._pick_audio_player()
        self._edge_temporarily_disabled = False
        self._edge_retry_at = 0.0

        if self._provider != TTS_PROVIDER:
            logger.warning("Noma'lum TTS provider '%s', Edge ishlatiladi.", TTS_PROVIDER)

        if self._enabled:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            logger.info("TTS engine ishga tushdi: provider=%s voice=%s", self._provider, TTS_EDGE_VOICE)
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

    def _pick_audio_player(self) -> list[str] | None:
        players = [
            ("afplay", ["afplay"]),
            ("ffplay", ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]),
            ("mpg123", ["mpg123", "-q"]),
            ("mpv", ["mpv", "--no-video", "--really-quiet"]),
        ]
        for binary, command in players:
            if shutil.which(binary):
                return command
        return None

    def _play_audio_file_windows(self, audio_path: Path) -> None:
        powershell = shutil.which("powershell.exe") or shutil.which("powershell") or shutil.which("pwsh")
        if not powershell:
            raise RuntimeError("Windows audio playback uchun PowerShell topilmadi")

        script = (
            "Add-Type -AssemblyName presentationCore; "
            "$path = [System.IO.Path]::GetFullPath($args[0]); "
            "$player = New-Object System.Windows.Media.MediaPlayer; "
            "$player.Open((New-Object System.Uri($path))); "
            "while (-not $player.NaturalDuration.HasTimeSpan) { Start-Sleep -Milliseconds 100 }; "
            "$player.Volume = 1.0; "
            "$player.Play(); "
            "$duration = [Math]::Ceiling($player.NaturalDuration.TimeSpan.TotalMilliseconds) + 250; "
            "Start-Sleep -Milliseconds $duration; "
            "$player.Stop(); "
            "$player.Close();"
        )
        command = [powershell]
        if os.path.basename(powershell).lower().startswith("powershell"):
            command.append("-STA")
        command.extend(
            [
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
                str(audio_path.resolve()),
            ]
        )
        subprocess.run(command, check=False)

    def _prepare_uzbek_text(self, text: str) -> str:
        text = text.strip()
        if not text:
            return text

        text = (
            text.replace("`", "'")
            .replace("’", "'")
            .replace("‘", "'")
            .replace("ʼ", "'")
            .replace("ʻ", "'")
        )
        text = re.sub(r"([OoGg])'", r"\1ʻ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

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

    def _prepare_fallback_text(self, text: str) -> str:
        if TTS_LANGUAGE == "uz":
            return self._normalize_uzbek_text(text)
        return text

    def _prepare_edge_text(self, text: str) -> str:
        if TTS_LANGUAGE == "uz":
            return self._prepare_uzbek_text(text)
        return re.sub(r"\s+", " ", text).strip()

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

    def _configure_engine_voice(self, engine) -> None:
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

    def _should_use_edge(self) -> bool:
        if self._provider not in {"edge", "auto"}:
            return False
        if self._edge_temporarily_disabled:
            return False
        if time.monotonic() < self._edge_retry_at:
            return False
        return bool(TTS_EDGE_VOICE)

    def _edge_cache_path(self, text: str) -> Path:
        key = "|".join([TTS_EDGE_VOICE, TTS_EDGE_RATE, TTS_EDGE_VOLUME, text])
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return Path(TTS_CACHE_DIR) / f"{digest}.mp3"

    async def _write_edge_audio(self, text: str, output_path: str) -> None:
        import edge_tts

        communicate = edge_tts.Communicate(
            text=text,
            voice=TTS_EDGE_VOICE,
            rate=TTS_EDGE_RATE,
            volume=TTS_EDGE_VOLUME,
        )
        await communicate.save(output_path)

    def _ensure_edge_audio(self, text: str) -> Path:
        cache_path = self._edge_cache_path(text)
        if cache_path.exists() and cache_path.stat().st_size > 0:
            return cache_path

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            prefix=f"{cache_path.stem}.",
            suffix=".tmp.mp3",
            dir=str(cache_path.parent),
        )
        os.close(fd)
        try:
            asyncio.run(self._write_edge_audio(text, tmp_path))
            if os.path.getsize(tmp_path) <= 0:
                raise RuntimeError("Edge TTS bo'sh audio qaytardi")
            os.replace(tmp_path, cache_path)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        return cache_path

    def _play_audio_file(self, audio_path: Path) -> None:
        if sys.platform.startswith("win"):
            self._play_audio_file_windows(audio_path)
            return
        if not self._audio_player:
            raise RuntimeError("MP3 audio player topilmadi (afplay/ffplay/mpg123/mpv)")
        subprocess.run([*self._audio_player, str(audio_path)], check=False)

    def _speak_edge(self, text: str) -> None:
        prepared_text = self._prepare_edge_text(text)
        if not prepared_text:
            return
        audio_path = self._ensure_edge_audio(prepared_text)
        self._play_audio_file(audio_path)

    def _ensure_pyttsx3_engine(self):
        if self._pyttsx3_engine is not None:
            return self._pyttsx3_engine

        import pyttsx3

        engine = pyttsx3.init()
        engine.setProperty("rate", TTS_RATE)
        engine.setProperty("volume", TTS_VOLUME)
        self._configure_engine_voice(engine)
        self._pyttsx3_engine = engine
        return engine

    def _speak_system(self, text: str) -> None:
        prepared_text = self._prepare_fallback_text(text)
        if not prepared_text:
            return

        if self._say_available:
            if not self._say_voice_checked:
                self._say_voice = self._pick_say_voice()
                self._say_voice_checked = True
                if self._say_voice:
                    logger.info("TTS say fallback voice tanlandi: %s", self._say_voice)
                else:
                    logger.info("TTS say default fallback voice ishlatiladi.")

            cmd = ["say", "-r", str(TTS_RATE)]
            if self._say_voice:
                cmd.extend(["-v", self._say_voice])
            cmd.append(prepared_text)
            subprocess.run(cmd, check=False)
            return

        engine = self._ensure_pyttsx3_engine()
        engine.say(prepared_text)
        engine.runAndWait()

    def _run(self):
        while True:
            try:
                text = self._q.get(timeout=0.5)
                if text is None:
                    break

                if self._should_use_edge():
                    try:
                        self._speak_edge(text)
                        continue
                    except Exception as e:
                        logger.warning("Edge Uzbek TTS ishlamadi, fallback ishlatiladi: %s", e)
                        if self._provider == "auto":
                            self._edge_temporarily_disabled = True
                        else:
                            self._edge_retry_at = time.monotonic() + 30.0

                self._speak_system(text)
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
