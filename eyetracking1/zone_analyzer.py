import time
import logging
from typing import Optional, Tuple

try:
    import pyautogui
    _SCREEN_SIZE = pyautogui.size()
except Exception:
    _SCREEN_SIZE = (1920, 1080)

from settings import SCREEN_ZONES, ZONE_DWELL_SEC, ZONE_COOLDOWN_SEC

logger = logging.getLogger(__name__)


class ZoneAnalyzer:
    """
    Ekranni 5 zonaga bo'ladi.
    Foydalanuvchi bir zonada ZONE_DWELL_SEC soniya qarab tursa → trigger.
    Trigger keyin ZONE_COOLDOWN_SEC kutiladi (spam oldini olish).
    Markaz zonasi (kichikroq maydon) ustun — overlap bo'lsa markaz g'alaba qiladi.
    """

    def __init__(self):
        self.sw, self.sh = _SCREEN_SIZE
        self._zone_start: float = 0.0
        self._current_zone: int = -1
        self._last_trigger: dict = {}
        self._fired_this_session: list = []

    def update(self, sx: int, sy: int) -> Optional[dict]:
        nx = sx / self.sw
        ny = sy / self.sh
        zone_idx = self._get_zone(nx, ny)

        if zone_idx != self._current_zone:
            self._current_zone = zone_idx
            self._zone_start   = time.time()
            return None

        if zone_idx < 0:
            return None

        elapsed  = time.time() - self._zone_start
        progress = min(1.0, elapsed / ZONE_DWELL_SEC)

        last_t = self._last_trigger.get(zone_idx, 0.0)
        if time.time() - last_t < ZONE_COOLDOWN_SEC:
            return None

        if progress >= 1.0:
            self._last_trigger[zone_idx] = time.time()
            zone_info = SCREEN_ZONES[zone_idx]
            result = {
                "zone_idx":  zone_idx,
                "zone_name": zone_info[4],
                "message":   zone_info[5],
                "screen_x":  sx,
                "screen_y":  sy,
            }
            self._fired_this_session.append(result)
            logger.info(f"ZONA TRIGGER: {zone_info[4]} — {zone_info[5]}")
            return result

        return None

    def get_progress(self, sx: int, sy: int) -> Tuple[int, float]:
        nx, ny = sx / self.sw, sy / self.sh
        zi = self._get_zone(nx, ny)
        if zi < 0 or zi != self._current_zone:
            return -1, 0.0
        elapsed  = time.time() - self._zone_start
        progress = min(1.0, elapsed / ZONE_DWELL_SEC)
        return zi, progress

    def _get_zone(self, nx: float, ny: float) -> int:
        """
        Qaysi zonada ekanligini topadi.
        Bir nechta zona ustma-ust kelsa, eng kichik maydoni (markaz) ustun.
        """
        matched = []
        for i, (xmn, ymn, xmx, ymx, *_) in enumerate(SCREEN_ZONES):
            if xmn <= nx <= xmx and ymn <= ny <= ymx:
                matched.append(i)
        if not matched:
            return -1
        # Kichikroq zona ustun (markaz = 0.09 maydon, boshqalar = 0.25)
        def area(i):
            z = SCREEN_ZONES[i]
            return (z[2] - z[0]) * (z[3] - z[1])
        return min(matched, key=area)

    def reset_zone(self):
        self._current_zone = -1
        self._zone_start   = time.time()

    @property
    def current_zone(self) -> int:
        return self._current_zone
