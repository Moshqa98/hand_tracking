"""
Управление компьютером жестами руки через веб-камеру.
Использует MediaPipe Tasks API (0.10.30+).

Установка зависимостей:
    pip install opencv-python mediapipe pyautogui pycaw comtypes

Жесты:
    Указательный палец вверх              — двигать курсор
    Щипок (большой + указательный)        — левый клик (ЛКМ)
    Двойной щипок (2 быстрых)             — двойной клик
    Указательный + средний вверх          — правый клик (ПКМ)
    Ладонь раскрыта + поворот влево/вправо — Alt+Tab переключение окон
    Кулак + расстояние большой-указательный — громкость (вместе=0%, врозь=100%)
    Кулак (без движения)                  — пауза

Управление:
    Q или ESC — выход
"""

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
import pyautogui
import time
import urllib.request
import os
import math

# Громкость через pycaw (Windows)
try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume_ctrl = cast(interface, POINTER(IAudioEndpointVolume))
    VOL_MIN, VOL_MAX, _ = volume_ctrl.GetVolumeRange()
    HAS_PYCAW = True
    print(f"Pycaw: громкость {VOL_MIN:.0f}..{VOL_MAX:.0f} dB")
except Exception as e:
    HAS_PYCAW = False
    volume_ctrl = None
    print(f"Pycaw недоступен ({e}), громкость через клавиши.")

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

# Landmark indices
WRIST = 0
THUMB_TIP = 4
THUMB_MCP = 2
INDEX_TIP = 8
INDEX_PIP = 6
INDEX_MCP = 5
MIDDLE_TIP = 12
MIDDLE_PIP = 10
MIDDLE_MCP = 9
RING_TIP = 16
RING_PIP = 14
PINKY_TIP = 20
PINKY_PIP = 18

# Настройки
SCREEN_W, SCREEN_H = pyautogui.size()
SMOOTHING = 5
CLICK_DIST = 0.04
DOUBLE_CLICK_TIME = 0.4   # Макс время между двумя щипками для двойного клика
PALM_ROTATE_THRESH = 15   # Градусы поворота ладони для Alt+Tab
VOL_DIST_MIN = 0.03       # Мин расстояние (пальцы вместе)
VOL_DIST_MAX = 0.20       # Макс расстояние (пальцы врозь)


def download_model():
    model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hand_landmarker.task")
    if not os.path.exists(model_path):
        url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
        print(f"Скачиваю модель... {url}")
        urllib.request.urlretrieve(url, model_path)
        print("Модель скачана.")
    return model_path


def dist(p1, p2):
    return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)


def is_finger_up(landmarks, tip_idx, pip_idx):
    return landmarks[tip_idx].y < landmarks[pip_idx].y


def get_palm_angle(landmarks):
    """Угол наклона ладони (градусы). 0 = вертикально, +/- = наклон."""
    wrist = landmarks[WRIST]
    middle_mcp = landmarks[MIDDLE_MCP]
    dx = middle_mcp.x - wrist.x
    dy = middle_mcp.y - wrist.y
    angle = math.degrees(math.atan2(dx, -dy))
    return angle


def set_volume(level):
    """Устанавливает громкость 0.0..1.0"""
    level = max(0.0, min(1.0, level))
    if HAS_PYCAW and volume_ctrl:
        vol_db = VOL_MIN + level * (VOL_MAX - VOL_MIN)
        volume_ctrl.SetMasterVolumeLevel(vol_db, None)


def get_volume():
    """Текущая громкость 0.0..1.0"""
    if HAS_PYCAW and volume_ctrl:
        current = volume_ctrl.GetMasterVolumeLevel()
        if VOL_MAX != VOL_MIN:
            return (current - VOL_MIN) / (VOL_MAX - VOL_MIN)
    return 0.5


def get_mode(landmarks):
    """
    Определяет режим:
    'move'    — только указательный вверх
    'pinch'   — большой + указательный сжаты
    'rclick'  — указательный + средний вверх
    'palm'    — все пальцы вверх (переключение окон)
    'volume'  — кулак (средний, безымянный, мизинец согнуты) — громкость по расстоянию thumb-index
    'idle'    — неопределённо
    """
    index_up = is_finger_up(landmarks, INDEX_TIP, INDEX_PIP)
    middle_up = is_finger_up(landmarks, MIDDLE_TIP, MIDDLE_PIP)
    ring_up = is_finger_up(landmarks, RING_TIP, RING_PIP)
    pinky_up = is_finger_up(landmarks, PINKY_TIP, PINKY_PIP)

    thumb_index = dist(landmarks[THUMB_TIP], landmarks[INDEX_TIP])

    # Щипок
    if thumb_index < CLICK_DIST:
        return 'pinch'

    # Все пальцы — ладонь (Alt+Tab)
    if index_up and middle_up and ring_up and pinky_up:
        return 'palm'

    # Указательный + средний — ПКМ
    if index_up and middle_up and not ring_up and not pinky_up:
        return 'rclick'

    # Только указательный — движение
    if index_up and not middle_up and not ring_up and not pinky_up:
        return 'move'

    # Все основные согнуты — режим громкости
    if not index_up and not middle_up and not ring_up and not pinky_up:
        return 'volume'

    return 'idle'


def main():
    model_path = download_model()

    detection_result = [None]

    def result_callback(result, output_image, timestamp_ms):
        detection_result[0] = result

    base_options = mp_python.BaseOptions(model_asset_path=model_path)
    options = vision.HandLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.LIVE_STREAM,
        num_hands=1,
        min_hand_detection_confidence=0.7,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
        result_callback=result_callback,
    )

    detector = vision.HandLandmarker.create_from_options(options)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Ошибка: не удалось открыть камеру!")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print("Камера запущена!")
    print("Указательный=курсор | Щипок=клик | 2xЩипок=двойной клик")
    print("2 пальца=ПКМ | Ладонь+поворот=Alt+Tab | Кулак=громкость")
    print("Q / ESC — выход")

    prev_time = time.time()
    timestamp = 0

    # Курсор
    smooth_x = SCREEN_W // 2
    smooth_y = SCREEN_H // 2

    # Клики
    pinch_done = False
    pinch_released_time = 0.0
    pinch_count = 0
    click_pending = False
    click_pending_time = 0.0
    rclick_done = False

    # Alt+Tab
    alt_tab_active = False
    palm_prev_angle = None
    last_tab_time = 0.0

    # Громкость
    current_vol = get_volume()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        timestamp += 33
        detector.detect_async(mp_image, timestamp)

        curr_time = time.time()
        fps = 1 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 0
        prev_time = curr_time

        result = detection_result[0]
        mode = 'idle'
        vol_display = None

        if result and result.hand_landmarks:
            landmarks = result.hand_landmarks[0]
            mode = get_mode(landmarks)

            index_x = landmarks[INDEX_TIP].x
            index_y = landmarks[INDEX_TIP].y

            # Рисуем руку
            for lm in landmarks:
                px, py = int(lm.x * w), int(lm.y * h)
                cv2.circle(frame, (px, py), 3, (0, 255, 0), -1)

            ix, iy = int(index_x * w), int(index_y * h)
            cv2.circle(frame, (ix, iy), 10, (255, 0, 255), -1)

            # === ДВИЖЕНИЕ КУРСОРА ===
            if mode == 'move':
                margin = 0.15
                norm_x = (index_x - margin) / (1.0 - 2 * margin)
                norm_y = (index_y - margin) / (1.0 - 2 * margin)
                norm_x = max(0.0, min(1.0, norm_x))
                norm_y = max(0.0, min(1.0, norm_y))

                target_x = int(norm_x * SCREEN_W)
                target_y = int(norm_y * SCREEN_H)

                smooth_x += (target_x - smooth_x) / SMOOTHING
                smooth_y += (target_y - smooth_y) / SMOOTHING
                pyautogui.moveTo(int(smooth_x), int(smooth_y))

                pinch_done = False
                rclick_done = False
                palm_prev_angle = None
                if alt_tab_active:
                    pyautogui.keyUp('alt')
                    alt_tab_active = False

            # === ЩИПОК / ДВОЙНОЙ КЛИК ===
            elif mode == 'pinch':
                if not pinch_done:
                    pinch_done = True
                    now = time.time()

                    if pinch_count == 1 and (now - pinch_released_time) < DOUBLE_CLICK_TIME:
                        # Двойной клик
                        pyautogui.doubleClick()
                        pinch_count = 0
                        click_pending = False
                    else:
                        pinch_count = 1
                        click_pending = True
                        click_pending_time = now

                rclick_done = False
                palm_prev_angle = None

            # === ПКМ ===
            elif mode == 'rclick':
                if not rclick_done:
                    pyautogui.rightClick()
                    rclick_done = True
                pinch_done = False
                palm_prev_angle = None
                if alt_tab_active:
                    pyautogui.keyUp('alt')
                    alt_tab_active = False

            # === ЛАДОНЬ — ALT+TAB ===
            elif mode == 'palm':
                angle = get_palm_angle(landmarks)

                if palm_prev_angle is not None:
                    delta = angle - palm_prev_angle
                    now = time.time()

                    if abs(delta) > PALM_ROTATE_THRESH and (now - last_tab_time) > 0.5:
                        if not alt_tab_active:
                            pyautogui.keyDown('alt')
                            alt_tab_active = True

                        if delta > 0:
                            pyautogui.press('tab')
                        else:
                            pyautogui.hotkey('shift', 'tab')

                        last_tab_time = now
                        palm_prev_angle = angle
                else:
                    palm_prev_angle = angle

                pinch_done = False
                rclick_done = False

            # === КУЛАК — ГРОМКОСТЬ ===
            elif mode == 'volume':
                thumb_index = dist(landmarks[THUMB_TIP], landmarks[INDEX_TIP])

                # Маппим расстояние на 0..1
                vol_level = (thumb_index - VOL_DIST_MIN) / (VOL_DIST_MAX - VOL_DIST_MIN)
                vol_level = max(0.0, min(1.0, vol_level))

                set_volume(vol_level)
                current_vol = vol_level
                vol_display = vol_level

                # Рисуем линию thumb-index
                tx, ty = int(landmarks[THUMB_TIP].x * w), int(landmarks[THUMB_TIP].y * h)
                cv2.line(frame, (tx, ty), (ix, iy), (0, 255, 255), 3)

                pinch_done = False
                rclick_done = False
                palm_prev_angle = None
                if alt_tab_active:
                    pyautogui.keyUp('alt')
                    alt_tab_active = False

            # === IDLE ===
            else:
                pinch_done = False
                rclick_done = False
                palm_prev_angle = None
                if alt_tab_active:
                    pyautogui.keyUp('alt')
                    alt_tab_active = False

            # Обработка отложенного одиночного клика
            if click_pending and not pinch_done:
                now = time.time()
                if (now - click_pending_time) > DOUBLE_CLICK_TIME:
                    pyautogui.click()
                    click_pending = False
                    pinch_count = 0

            # Запоминаем время отпускания щипка
            if mode != 'pinch' and pinch_done:
                pinch_released_time = time.time()
                pinch_done = False

        else:
            # Нет руки — сбрасываем всё
            pinch_done = False
            rclick_done = False
            palm_prev_angle = None
            if alt_tab_active:
                pyautogui.keyUp('alt')
                alt_tab_active = False

        # === ОТРИСОВКА UI ===
        mode_colors = {
            'move': (0, 255, 0),
            'pinch': (0, 0, 255),
            'rclick': (255, 0, 0),
            'palm': (255, 165, 0),
            'volume': (0, 255, 255),
            'idle': (128, 128, 128),
        }
        mode_names = {
            'move': 'MOVE',
            'pinch': 'CLICK',
            'rclick': 'RIGHT CLICK',
            'palm': 'ALT+TAB',
            'volume': 'VOLUME',
            'idle': 'IDLE',
        }

        color = mode_colors.get(mode, (255, 255, 255))
        cv2.putText(frame, f"FPS: {int(fps)}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, mode_names.get(mode, ''), (10, 65),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3)

        # Полоска громкости
        vol_bar_x = w - 40
        vol_bar_h = h - 100
        vol_bar_y = 50
        cv2.rectangle(frame, (vol_bar_x, vol_bar_y), (vol_bar_x + 20, vol_bar_y + vol_bar_h),
                      (80, 80, 80), 2)
        filled_h = int(current_vol * vol_bar_h)
        cv2.rectangle(frame, (vol_bar_x, vol_bar_y + vol_bar_h - filled_h),
                      (vol_bar_x + 20, vol_bar_y + vol_bar_h),
                      (0, 255, 255), -1)
        cv2.putText(frame, f"{int(current_vol * 100)}%", (vol_bar_x - 15, vol_bar_y + vol_bar_h + 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        cv2.putText(frame, "VOL", (vol_bar_x - 5, vol_bar_y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

        # Подсказки
        hints = [
            "Index = Move cursor",
            "Pinch = Click (2x = DblClick)",
            "Index+Middle = Right Click",
            "Open Palm + Rotate = Alt+Tab",
            "Fist = Volume (thumb-index dist)",
        ]
        for i, hint in enumerate(hints):
            cv2.putText(frame, hint, (10, h - 20 - i * 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

        cv2.imshow("Hand Control", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            break

    if alt_tab_active:
        pyautogui.keyUp('alt')

    cap.release()
    cv2.destroyAllWindows()
    detector.close()
    print("Завершено.")


if __name__ == "__main__":
    main()
