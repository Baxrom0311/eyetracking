import logging
import sys
import time

import cv2

from camera import CameraError, CameraManager
from face_tracker import FaceTracker
from settings import (
    CAMERA_HEIGHT,
    CAMERA_READ_FAIL_LIMIT,
    CAMERA_WIDTH,
    DEBUG_MODE,
    LOG_FILE,
    OVERLAY_WINDOW_NAME,
    PREVIEW_MIRROR,
)


logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, mode="a"),
    ],
)
logger = logging.getLogger(__name__)


def main() -> int:
    camera = CameraManager()
    tracker = None
    empty_frames = 0

    try:
        tracker = FaceTracker()
        camera.open()
        cv2.namedWindow(OVERLAY_WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(OVERLAY_WINDOW_NAME, CAMERA_WIDTH, CAMERA_HEIGHT)

        while True:
            frame = camera.read()
            if frame is None:
                empty_frames += 1
                if empty_frames >= CAMERA_READ_FAIL_LIMIT:
                    raise CameraError("Kamera frame bermayapti.")
                time.sleep(0.01)
                continue

            empty_frames = 0
            if PREVIEW_MIRROR:
                frame = cv2.flip(frame, 1)

            face_data = tracker.process(frame)
            tracker.draw_debug(frame, face_data)
            status = "Face found" if face_data.found else "No face"
            cv2.putText(
                frame,
                f"test_face.py  {status}",
                (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 220, 120),
                2,
            )
            cv2.putText(
                frame,
                "Q / ESC - exit",
                (12, frame.shape[0] - 16),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (180, 180, 180),
                1,
            )
            cv2.imshow(OVERLAY_WINDOW_NAME, frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                return 0
    except CameraError as exc:
        logger.error(str(exc))
        print(f"\nXATO: {exc}\n")
        return 1
    except Exception as exc:
        logger.error("Face test ishga tushmadi: %s", exc)
        print(f"\nXATO: {exc}\n")
        return 1
    finally:
        camera.close()
        if tracker is not None:
            tracker.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    raise SystemExit(main())
