from enum import Enum, auto
import time
import logging
from settings import HEAD_AWAY_DELAY_SEC, NO_FACE_DELAY_SEC

logger = logging.getLogger(__name__)


class State(Enum):
    IDLE         = auto()   # Dastur kutmoqda, kamera yopiq
    INIT         = auto()   # Kamera + MP yuklanmoqda
    CALIBRATING  = auto()   # Kalibrasiya oynasi ochiq
    TRACKING     = auto()   # Normal ishlash
    DWELL_ZONE   = auto()   # Zona ustida, 10s timer
    ZONE_FIRED   = auto()   # 10s to'ldi, xabar yuborildi
    NO_FACE      = auto()   # Yuz topilmadi
    LOST_GAZE    = auto()   # Yuz bor, iris yo'q
    LOW_LIGHT    = auto()   # Yorug'lik yetarli emas
    CAM_ERROR    = auto()   # Kamera xatosi
    HEAD_AWAY    = auto()   # Bosh juda chetga ketdi
    RECALIBRATE  = auto()   # Qayta kalibrasiya


# Har holat uchun foydalanuvchiga ko'rsatiladigan xabar
STATE_MESSAGES = {
    State.IDLE:        "Eye Mode o'chiq",
    State.INIT:        "Yuklanmoqda...",
    State.CALIBRATING: "Kalibrasiya — nuqtaga qarang",
    State.TRACKING:    "Kuzatilmoqda",
    State.DWELL_ZONE:  "Zona aniqlanmoqda...",
    State.ZONE_FIRED:  "Xabar yuborildi!",
    State.NO_FACE:     "Yuz topilmadi — kameraga qarang",
    State.LOST_GAZE:   "Ko'zni ochiq saqlang",
    State.LOW_LIGHT:   "Yorug'lik yetarli emas",
    State.CAM_ERROR:   "Kamera xatosi",
    State.HEAD_AWAY:   "Boshingizni to'g'rilang",
    State.RECALIBRATE: "Qayta kalibrasiya...",
}

# Xato holatlari (qizil banner)
ERROR_STATES = {
    State.NO_FACE, State.LOST_GAZE, State.LOW_LIGHT,
    State.CAM_ERROR, State.HEAD_AWAY
}


class StateMachine:
    def __init__(self):
        self._state     = State.IDLE
        self._prev      = State.IDLE
        self._changed_t = time.time()
        # NO_FACE debounce
        self._no_face_start = 0.0
        self._head_away_start = 0.0
        self.NO_FACE_DELAY  = NO_FACE_DELAY_SEC
        self.HEAD_AWAY_DELAY = HEAD_AWAY_DELAY_SEC

    # ── Joriy holat ──────────────────────────────────────
    @property
    def state(self) -> State:
        return self._state

    @property
    def message(self) -> str:
        return STATE_MESSAGES.get(self._state, "")

    @property
    def is_error(self) -> bool:
        return self._state in ERROR_STATES

    @property
    def is_tracking(self) -> bool:
        return self._state in (State.TRACKING, State.DWELL_ZONE, State.ZONE_FIRED)

    # ── Holat o'zgartirish ────────────────────────────────
    def transition(self, new_state: State):
        if new_state == self._state:
            return
        logger.debug(f"State: {self._state.name} → {new_state.name}")
        self._prev      = self._state
        self._state     = new_state
        self._changed_t = time.time()

    # ── Har frame da chaqiriladigan avtomatik tekshiruvlar ─
    def update_from_frame(self, face_found: bool, iris_found: bool,
                          low_light: bool, cam_ok: bool,
                          head_away: bool = False):
        """
        Kamera / yuz holatiga qarab avtomatik transition.
        """
        if not cam_ok:
            self.transition(State.CAM_ERROR)
            return

        # Faqat TRACKING / DWELL da NO_FACE tekshiramiz
        if self._state in (State.TRACKING, State.DWELL_ZONE,
                           State.ZONE_FIRED, State.NO_FACE,
                           State.LOST_GAZE, State.HEAD_AWAY,
                           State.LOW_LIGHT):
            if not face_found:
                now = time.time()
                if self._no_face_start == 0.0:
                    self._no_face_start = now
                elif now - self._no_face_start >= self.NO_FACE_DELAY:
                    self.transition(State.NO_FACE)
                return
            self._no_face_start = 0.0
            if low_light:
                if self._state != State.LOW_LIGHT:
                    self.transition(State.LOW_LIGHT)
                return
            if head_away:
                now = time.time()
                if self._head_away_start == 0.0:
                    self._head_away_start = now
                elif now - self._head_away_start >= self.HEAD_AWAY_DELAY:
                    self.transition(State.HEAD_AWAY)
                return
            self._head_away_start = 0.0
            if not iris_found:
                self.transition(State.LOST_GAZE)
            else:
                # Yuz va iris topildi — tracking ga qayt
                if self._state in (State.NO_FACE, State.LOST_GAZE,
                                   State.HEAD_AWAY, State.LOW_LIGHT):
                    self.transition(State.TRACKING)

    def time_in_state(self) -> float:
        return time.time() - self._changed_t
