import cv2
import numpy as np
import time
from typing import Tuple, Optional
from settings import (
    OVERLAY_SHOW_FPS, OVERLAY_SHOW_ZONES, OVERLAY_CURSOR_RADIUS,
    OVERLAY_CURSOR_COLOR, OVERLAY_DWELL_COLOR, OVERLAY_ERROR_COLOR,
    OVERLAY_FONT_SCALE, SCREEN_ZONES, ZONE_DWELL_SEC
)
from state_machine import State, ERROR_STATES

try:
    import pyautogui
except Exception:
    pyautogui = None


class OverlayUI:
    """
    OpenCV kamera oynasiga ma'lumotlarni chizadi:
    - Iris cursor nuqtasi
    - Zona progressi (arc)
    - Holat banneri
    - FPS
    - Zonalar chegarasi (debug)
    """

    def __init__(self):
        self.sw, self.sh = pyautogui.size()
        self._banner_text = ""
        self._banner_t    = 0.0
        self._banner_dur  = 3.0   # sekund ko'rinadi

    def draw(self, frame: np.ndarray, state: State,
             gaze_screen: Optional[Tuple[int, int]],
             zone_idx: int, zone_progress: float,
             fps: float, brightness: int,
             dwell_progress: float = 0.0) -> np.ndarray:

        h, w = frame.shape[:2]

        # ── Zonalar chegarasi ─────────────────────────────
        if OVERLAY_SHOW_ZONES and state != State.CALIBRATING:
            self._draw_zones(frame, w, h, zone_idx, zone_progress)

        # ── Gaze cursor ───────────────────────────────────
        if gaze_screen and state not in ERROR_STATES:
            self._draw_cursor(frame, gaze_screen, w, h,
                              dwell_progress)

        # ── Holat banneri ─────────────────────────────────
        self._draw_state_banner(frame, state, w, h)

        # ── FPS + Brightness ─────────────────────────────
        if OVERLAY_SHOW_FPS:
            self._draw_stats(frame, fps, brightness, state)

        # ── Vaqtinchalik banner (zone fired, xabar) ───────
        self._draw_temp_banner(frame, w, h)

        return frame

    # ── Zonalar ───────────────────────────────────────────
    def _draw_zones(self, frame, w, h, active_zone, progress):
        for i, (xmn, ymn, xmx, ymx, name, _) in enumerate(SCREEN_ZONES):
            x1 = int(xmn * w); y1 = int(ymn * h)
            x2 = int(xmx * w); y2 = int(ymx * h)
            if i == active_zone:
                # Aktiv zona — yashil chegarasi
                alpha = 0.12 + 0.08 * progress
                overlay = frame.copy()
                cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 220, 120), -1)
                frame[:] = cv2.addWeighted(overlay, alpha, frame, 1-alpha, 0)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 120), 2)
                # Progress bar (pastki chiziq)
                bar_w = int((x2 - x1) * progress)
                cv2.rectangle(frame, (x1, y2-4), (x1+bar_w, y2), (0,220,120), -1)
                # Zona nomi
                cv2.putText(frame, name, (x1+8, y1+22),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,220,120), 1)
                # Timer
                remaining = max(0.0, ZONE_DWELL_SEC * (1.0 - progress))
                remaining = f"{remaining:.1f}s"
                cv2.putText(frame, remaining, (x1+8, y1+42),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180,255,180), 1)
            else:
                cv2.rectangle(frame, (x1, y1), (x2, y2),
                              (60, 60, 60), 1)
                cv2.putText(frame, name, (x1+6, y1+18),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100,100,100), 1)

    # ── Gaze cursor ───────────────────────────────────────
    def _draw_cursor(self, frame, gaze_screen, w, h, dwell_progress):
        sx, sy = gaze_screen
        # Kamera oynasiga nisbatan niqoblash
        cx = int(sx / self.sw * w)
        cy = int(sy / self.sh * h)
        cx = max(0, min(w-1, cx))
        cy = max(0, min(h-1, cy))

        r = OVERLAY_CURSOR_RADIUS
        color = OVERLAY_CURSOR_COLOR

        # Tashqi halqa
        cv2.circle(frame, (cx, cy), r+4, color, 1)
        # Markaziy nuqta
        cv2.circle(frame, (cx, cy), 5, color, -1)
        # Crosshair
        cv2.line(frame, (cx-r, cy), (cx-6, cy), color, 1)
        cv2.line(frame, (cx+6, cy), (cx+r, cy), color, 1)
        cv2.line(frame, (cx, cy-r), (cx, cy-6), color, 1)
        cv2.line(frame, (cx, cy+6), (cx, cy+r), color, 1)

        # Dwell arc
        if dwell_progress > 0.01:
            angle = int(360 * dwell_progress)
            cv2.ellipse(frame, (cx, cy), (r+2, r+2), -90,
                        0, angle, OVERLAY_DWELL_COLOR, 2)

    # ── Holat banneri ─────────────────────────────────────
    def _draw_state_banner(self, frame, state: State, w, h):
        from state_machine import STATE_MESSAGES
        msg = STATE_MESSAGES.get(state, "")
        if not msg:
            return

        if state in ERROR_STATES:
            bg_color   = OVERLAY_ERROR_COLOR
            text_color = (255, 255, 255)
        elif state in (State.TRACKING, State.DWELL_ZONE, State.ZONE_FIRED):
            bg_color   = (30, 100, 30)
            text_color = (200, 255, 200)
        else:
            bg_color   = (40, 40, 40)
            text_color = (220, 220, 220)

        bar_h = 32
        cv2.rectangle(frame, (0, 0), (w, bar_h), bg_color, -1)
        cv2.putText(frame, f"  {msg}", (8, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 1)

    # ── Stats ─────────────────────────────────────────────
    def _draw_stats(self, frame, fps, brightness, state):
        h, w = frame.shape[:2]
        txt = f"FPS:{fps:.0f}  Light:{brightness}"
        cv2.putText(frame, txt, (w-160, h-12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (120,120,120), 1)

    # ── Vaqtinchalik banner ───────────────────────────────
    def show_banner(self, text: str, duration: float = 3.0):
        self._banner_text = text
        self._banner_t    = time.time()
        self._banner_dur  = duration

    def _draw_temp_banner(self, frame, w, h):
        if not self._banner_text:
            return
        if time.time() - self._banner_t > self._banner_dur:
            self._banner_text = ""
            return
        bh = 48
        y0 = h // 2 - bh // 2
        cv2.rectangle(frame, (0, y0), (w, y0+bh), (0, 80, 0), -1)
        text_size, _ = cv2.getTextSize(
            self._banner_text,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            2,
        )
        cv2.putText(frame, self._banner_text,
                    (max(10, (w - text_size[0]) // 2), y0+30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (100, 255, 150), 2)
