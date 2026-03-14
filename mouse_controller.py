import logging
import time

try:
    import pyautogui
    _HAS_PYAUTOGUI = True
except Exception:
    _HAS_PYAUTOGUI = False

from settings import (
    DWELL_CLICK_MS,
    DWELL_RADIUS_PX,
    DWELL_SUPPRESS_AFTER_ACTION_SEC,
    PYAUTOGUI_PAUSE,
)

logger = logging.getLogger(__name__)

# PyAutoGUI xavfsizlik sozlamalari
if _HAS_PYAUTOGUI:
    pyautogui.FAILSAFE   = True
    pyautogui.PAUSE      = PYAUTOGUI_PAUSE


class MouseController:
    """
    Gaze koordinatidan cursor harakatini va click larni boshqaradi.
    """

    def __init__(self):
        self._dwell_start = time.time()
        self._dwell_x     = 0
        self._dwell_y     = 0
        self._dwell_fired = False
        self._dwell_suppress_until = 0.0
        self._last_click_t = 0.0
        self._click_cooldown = 1.0   # sec — ketma-ket click oldini olish
        logger.info("MouseController tayyor.")

    # ── Cursor harakati ───────────────────────────────────
    def move(self, x: int, y: int):
        """Cursor ni shu koordinatga ko'chiradi."""
        try:
            pyautogui.moveTo(x, y, _pause=False)
        except pyautogui.FailSafeException:
            logger.warning("PyAutoGUI FailSafe — burchakka tegdi.")
        except Exception as e:
            logger.error(f"moveTo xatosi: {e}")

    def _consume_click(self) -> bool:
        now = time.time()
        if now - self._last_click_t < self._click_cooldown:
            return False
        self._last_click_t = now
        return True

    # ── Blink click ───────────────────────────────────────
    def blink_click(self, double: bool = False):
        """Blink aniqlanganda click qiladi."""
        if not self._consume_click():
            return
        try:
            if double:
                pyautogui.doubleClick(_pause=False)
                logger.debug("Double click (double blink)")
            else:
                pyautogui.click(_pause=False)
                logger.debug("Click (blink)")
        except Exception as e:
            logger.error(f"Click xatosi: {e}")

    def right_click(self):
        """Long blink = right click."""
        if not self._consume_click():
            return
        try:
            pyautogui.rightClick(_pause=False)
            logger.debug("Right click (long blink)")
        except Exception as e:
            logger.error(f"Right click xatosi: {e}")

    def left_click(self):
        """Oddiy left click."""
        if not self._consume_click():
            return False
        try:
            pyautogui.click(_pause=False)
            logger.debug("Left click")
            return True
        except Exception as e:
            logger.error(f"Left click xatosi: {e}")
            return False

    def suppress_dwell(self, x: int | None = None, y: int | None = None):
        now = time.time()
        self._dwell_start = now
        self._dwell_suppress_until = now + DWELL_SUPPRESS_AFTER_ACTION_SEC
        self._dwell_fired = True
        if x is not None and y is not None:
            self._dwell_x = x
            self._dwell_y = y

    # ── Dwell click ───────────────────────────────────────
    def update_dwell(self, x: int, y: int) -> float:
        """
        Cursor harakatsiz tursa dwell timer ishlaydi.
        0.0-1.0 progress qaytaradi. 1.0 = click vaqti.
        """
        dist = ((x - self._dwell_x)**2 + (y - self._dwell_y)**2) ** 0.5
        if dist > DWELL_RADIUS_PX:
            # Harakat bo'ldi — qayta boshlash
            self._dwell_start = time.time()
            self._dwell_x, self._dwell_y = x, y
            self._dwell_fired = False
            self._dwell_suppress_until = 0.0
            return 0.0

        if time.time() < self._dwell_suppress_until:
            return 0.0

        if self._dwell_fired:
            return 0.0

        elapsed = (time.time() - self._dwell_start) * 1000  # ms
        progress = min(1.0, elapsed / DWELL_CLICK_MS)

        if progress >= 1.0:
            if not self._dwell_fired and self.left_click():
                self._dwell_fired = True
                self._dwell_suppress_until = time.time() + DWELL_SUPPRESS_AFTER_ACTION_SEC
            return 0.0

        return progress

    def reset_dwell(self):
        self._dwell_start = time.time()
        self._dwell_x = 0
        self._dwell_y = 0
        self._dwell_fired = False
        self._dwell_suppress_until = 0.0
