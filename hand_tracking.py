"""
Отслеживание руки через веб-камеру.
Использует MediaPipe Tasks API (0.10.30+).

Установка зависимостей:
    pip install opencv-python mediapipe

Управление:
    Q или ESC — выход
"""

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
from mediapipe import solutions
import time
import urllib.request
import os


# Landmark indices
THUMB_TIP = 4
THUMB_IP = 3
INDEX_TIP = 8
INDEX_PIP = 6
MIDDLE_TIP = 12
MIDDLE_PIP = 10
RING_TIP = 16
RING_PIP = 14
PINKY_TIP = 20
PINKY_PIP = 18

FINGER_TIPS = [THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP]
FINGER_PIPS = [THUMB_IP, INDEX_PIP, MIDDLE_PIP, RING_PIP, PINKY_PIP]
FINGER_NAMES = ["Bolshoy", "Ukazat.", "Sredniy", "Bezymyan.", "Mizinec"]

# Connections for drawing hand skeleton
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),       # Thumb
    (0, 5), (5, 6), (6, 7), (7, 8),       # Index
    (0, 9), (9, 10), (10, 11), (11, 12),  # Middle
    (0, 13), (13, 14), (14, 15), (15, 16), # Ring
    (0, 17), (17, 18), (18, 19), (19, 20), # Pinky
    (5, 9), (9, 13), (13, 17),             # Palm
]


def download_model():
    """Скачивает модель hand_landmarker если её нет."""
    model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hand_landmarker.task")
    if not os.path.exists(model_path):
        url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
        print(f"Скачиваю модель... {url}")
        urllib.request.urlretrieve(url, model_path)
        print("Модель скачана.")
    return model_path


def count_fingers(landmarks, handedness):
    """Считает количество поднятых пальцев."""
    fingers_up = []

    # Большой палец — по оси X
    thumb_tip = landmarks[THUMB_TIP]
    thumb_ip = landmarks[THUMB_IP]

    if handedness == "Right":
        fingers_up.append(thumb_tip.x < thumb_ip.x)
    else:
        fingers_up.append(thumb_tip.x > thumb_ip.x)

    # Остальные — по оси Y
    for i in range(1, 5):
        tip = landmarks[FINGER_TIPS[i]]
        pip_joint = landmarks[FINGER_PIPS[i]]
        fingers_up.append(tip.y < pip_joint.y)

    return fingers_up


def get_gesture(fingers_up):
    """Определяет жест по поднятым пальцам."""
    total = sum(fingers_up)

    if total == 0:
        return "Kulak"
    if total == 5:
        return "Ladon"
    if fingers_up == [False, True, False, False, False]:
        return "Ukazanie"
    if fingers_up == [False, True, True, False, False]:
        return "Victory"
    if fingers_up == [True, False, False, False, True]:
        return "Rock!"
    if fingers_up == [True, True, False, False, False]:
        return "Pistolet"
    if fingers_up == [False, False, False, False, True]:
        return "Mizinec"
    if fingers_up == [True, False, False, False, False]:
        return "Like"

    return f"Palcev: {total}"


def draw_landmarks(frame, landmarks, w, h):
    """Рисует ключевые точки и соединения на кадре."""
    points = []
    for lm in landmarks:
        px, py = int(lm.x * w), int(lm.y * h)
        points.append((px, py))
        cv2.circle(frame, (px, py), 5, (0, 0, 255), -1)
        cv2.circle(frame, (px, py), 3, (255, 255, 255), -1)

    for start, end in HAND_CONNECTIONS:
        cv2.line(frame, points[start], points[end], (0, 255, 0), 2)


def main():
    model_path = download_model()

    # Результаты из callback
    detection_result = [None]
    result_timestamp = [0]

    def result_callback(result, output_image, timestamp_ms):
        detection_result[0] = result
        result_timestamp[0] = timestamp_ms

    # Настройка детектора
    base_options = mp_python.BaseOptions(model_asset_path=model_path)
    options = vision.HandLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.LIVE_STREAM,
        num_hands=2,
        min_hand_detection_confidence=0.7,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
        result_callback=result_callback,
    )

    detector = vision.HandLandmarker.create_from_options(options)

    # Захват видео
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Ошибка: не удалось открыть камеру!")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    print("Камера запущена. Покажите руку!")
    print("Нажмите Q или ESC для выхода.")

    prev_time = time.time()
    timestamp = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Ошибка чтения кадра.")
            break

        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape

        # Отправляем кадр в детектор
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        timestamp += 33  # ~30 FPS
        detector.detect_async(mp_image, timestamp)

        # FPS
        curr_time = time.time()
        fps = 1 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 0
        prev_time = curr_time
        cv2.putText(frame, f"FPS: {int(fps)}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        # Обработка результатов
        result = detection_result[0]

        if result and result.hand_landmarks:
            for idx, hand_lms in enumerate(result.hand_landmarks):
                handedness = result.handedness[idx][0].category_name
                confidence = result.handedness[idx][0].score
                hand_label = "Right" if handedness == "Right" else "Left"

                # Рисуем скелет
                draw_landmarks(frame, hand_lms, w, h)

                # Считаем пальцы
                fingers_up = count_fingers(hand_lms, handedness)
                gesture = get_gesture(fingers_up)
                total_up = sum(fingers_up)

                # Bounding box
                x_coords = [lm.x for lm in hand_lms]
                y_coords = [lm.y for lm in hand_lms]
                x_min = int(min(x_coords) * w) - 20
                y_min = int(min(y_coords) * h) - 20
                x_max = int(max(x_coords) * w) + 20
                y_max = int(max(y_coords) * h) + 20

                color = (0, 255, 0) if handedness == "Right" else (255, 0, 0)
                cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), color, 2)

                cv2.putText(frame, f"{hand_label} ({confidence:.0%})",
                            (x_min, y_min - 10), cv2.FONT_HERSHEY_SIMPLEX,
                            0.7, color, 2)

                cv2.putText(frame, gesture,
                            (x_min, y_max + 25), cv2.FONT_HERSHEY_SIMPLEX,
                            0.8, (0, 255, 255), 2)

                cv2.putText(frame, str(total_up),
                            (x_max - 30, y_min + 35), cv2.FONT_HERSHEY_SIMPLEX,
                            1.2, (0, 0, 255), 3)

                # Индикаторы пальцев
                base_x = 10 + idx * 350
                for i, (name, is_up) in enumerate(zip(FINGER_NAMES, fingers_up)):
                    clr = (0, 255, 0) if is_up else (0, 0, 200)
                    status = "^" if is_up else "v"
                    cv2.putText(frame, f"{name}: {status}",
                                (base_x, h - 80 + i * 18),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, clr, 1)
        else:
            cv2.putText(frame, "Ruka ne obnaruzhena",
                        (w // 2 - 150, h // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        cv2.imshow("Hand Tracking", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()
    detector.close()
    print("Завершено.")


if __name__ == "__main__":
    main()
