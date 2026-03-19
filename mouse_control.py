"""
Управление мышью жестами руки через веб-камеру.
Использует MediaPipe Tasks API (0.10.30+).

Установка зависимостей:
    pip install opencv-python mediapipe pyautogui

Жесты:
    Указательный палец вверх        — двигать курсор
    Указательный + большой сжать    — левый клик (ЛКМ)
    Указательный + средний вверх    — правый клик (ПКМ)
    Кулак                           — ничего (пауза)
    Ладонь (все пальцы)             — скролл (двигай вверх/вниз)

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

# Отключаем failsafe pyautogui (иначе в углу экрана крашится)
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

# Landmark indices
WRIST = 0
THUMB_TIP = 4
INDEX_TIP = 8
INDEX_PIP = 6
MIDDLE_TIP = 12
MIDDLE_PIP = 10
RING_TIP = 16
RING_PIP = 14
PINKY_TIP = 20
PINKY_PIP = 18

# Настройки
SCREEN_W, SCREEN_H = pyautogui.size()
SMOOTHING = 5          # Сглаживание движения (чем больше, тем плавнее)
CLICK_DIST = 0.04      # Порог расстояния для щипка (thumb-index)
SCROLL_SPEED = 15       # Скорость скролла


def download_model():
    """Скачивает модель hand_landmarker если её нет."""
    model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hand_landmarker.task")
    if not os.path.exists(model_path):
        url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
        print(f"Скачиваю модель... {url}")
        urllib.request.urlretrieve(url, model_path)
        print("Модель скачана.")
    return model_path


def distance(p1, p2):
    """Расстояние между двумя landmarks."""
    return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)


def is_finger_up(landmarks, tip_idx, pip_idx):
    """Проверяет, поднят ли палец."""
    return landmarks[tip_idx].y < landmarks[pip_idx].y


def get_mode(landmarks):
    """
    Определяет режим по жестам:
    'move'   — только указательный вверх (двигаем курсор)
    'lclick' — большой и указательный сжаты (щипок)
    'rclick' — указательный + средний вверх
    'scroll' — все 5 пальцев вверх (ладонь)
    'idle'   — кулак или неопределённо
    """
    index_up = is_finger_up(landmarks, INDEX_TIP, INDEX_PIP)
    middle_up = is_finger_up(landmarks, MIDDLE_TIP, MIDDLE_PIP)
    ring_up = is_finger_up(landmarks, RING_TIP, RING_PIP)
    pinky_up = is_finger_up(landmarks, PINKY_TIP, PINKY_PIP)

    thumb_index_dist = distance(landmarks[THUMB_TIP], landmarks[INDEX_TIP])

    # Щипок — ЛКМ
    if thumb_index_dist < CLICK_DIST and index_up:
        return 'lclick'

    # Указательный + средний — ПКМ
    if index_up and middle_up and not ring_up and not pinky_up:
        return 'rclick'

    # Все пальцы вверх — скролл
    if index_up and middle_up and ring_up and pinky_up:
        return 'scroll'

    # Только указательный — движение
    if index_up and not middle_up and not ring_up and not pinky_up:
        return 'move'

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

    print("Камера запущена. Управляйте мышью жестами!")
    print("Указательный — двигать | Щипок — ЛКМ | Два пальца — ПКМ | Ладонь — скролл")
    print("Q / ESC — выход")

    prev_time = time.time()
    timestamp = 0

    # Сглаживание курсора
    smooth_x = SCREEN_W // 2
    smooth_y = SCREEN_H // 2

    # Состояния кликов (чтобы не спамить)
    lclick_done = False
    rclick_done = False

    # Для скролла — запоминаем предыдущую Y позицию
    scroll_prev_y = None

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

        if result and result.hand_landmarks:
            landmarks = result.hand_landmarks[0]
            mode = get_mode(landmarks)

            # Позиция указательного пальца
            index_x = landmarks[INDEX_TIP].x
            index_y = landmarks[INDEX_TIP].y

            # Рисуем точки на кадре
            for lm in landmarks:
                px, py = int(lm.x * w), int(lm.y * h)
                cv2.circle(frame, (px, py), 3, (0, 255, 0), -1)

            # Рисуем кончик указательного крупнее
            ix, iy = int(index_x * w), int(index_y * h)
            cv2.circle(frame, (ix, iy), 10, (255, 0, 255), -1)

            if mode == 'move':
                # Маппим координаты пальца на экран
                # Зона управления — центральная часть кадра (чтобы не тянуться к краям)
                margin = 0.15
                norm_x = (index_x - margin) / (1.0 - 2 * margin)
                norm_y = (index_y - margin) / (1.0 - 2 * margin)
                norm_x = max(0.0, min(1.0, norm_x))
                norm_y = max(0.0, min(1.0, norm_y))

                target_x = int(norm_x * SCREEN_W)
                target_y = int(norm_y * SCREEN_H)

                # Сглаживание
                smooth_x += (target_x - smooth_x) / SMOOTHING
                smooth_y += (target_y - smooth_y) / SMOOTHING

                pyautogui.moveTo(int(smooth_x), int(smooth_y))

                lclick_done = False
                rclick_done = False
                scroll_prev_y = None

            elif mode == 'lclick':
                if not lclick_done:
                    pyautogui.click()
                    lclick_done = True
                rclick_done = False
                scroll_prev_y = None

            elif mode == 'rclick':
                if not rclick_done:
                    pyautogui.rightClick()
                    rclick_done = True
                lclick_done = False
                scroll_prev_y = None

            elif mode == 'scroll':
                if scroll_prev_y is not None:
                    delta = scroll_prev_y - index_y
                    if abs(delta) > 0.005:
                        pyautogui.scroll(int(delta * SCROLL_SPEED * 100))
                scroll_prev_y = index_y
                lclick_done = False
                rclick_done = False

            else:
                lclick_done = False
                rclick_done = False
                scroll_prev_y = None

        # Отображение на экране
        mode_colors = {
            'move': (0, 255, 0),
            'lclick': (0, 0, 255),
            'rclick': (255, 0, 0),
            'scroll': (255, 255, 0),
            'idle': (128, 128, 128),
        }
        mode_names = {
            'move': 'MOVE',
            'lclick': 'LEFT CLICK',
            'rclick': 'RIGHT CLICK',
            'scroll': 'SCROLL',
            'idle': 'IDLE',
        }

        color = mode_colors.get(mode, (255, 255, 255))
        cv2.putText(frame, f"FPS: {int(fps)}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, mode_names.get(mode, ''), (10, 65),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3)

        # Подсказки
        cv2.putText(frame, "Index up = Move", (10, h - 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
        cv2.putText(frame, "Pinch = LClick", (10, h - 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
        cv2.putText(frame, "Index+Middle = RClick", (10, h - 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
        cv2.putText(frame, "Palm = Scroll", (10, h - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

        cv2.imshow("Mouse Control", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()
    detector.close()
    print("Завершено.")


if __name__ == "__main__":
    main()
