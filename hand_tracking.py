"""
Отслеживание руки через веб-камеру.
Использует MediaPipe для детекции ключевых точек руки.

Установка зависимостей:
    pip install opencv-python mediapipe

Управление:
    Q или ESC — выход
"""

import cv2
import mediapipe as mp
import time


def main():
    # Инициализация MediaPipe Hands
    mp_hands = mp.solutions.hands
    mp_draw = mp.solutions.drawing_utils
    mp_styles = mp.solutions.drawing_styles

    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.5,
    )

    # Названия пальцев
    FINGER_NAMES = ["Большой", "Указательный", "Средний", "Безымянный", "Мизинец"]

    # Кончики пальцев (landmark indices)
    FINGER_TIPS = [
        mp_hands.HandLandmark.THUMB_TIP,
        mp_hands.HandLandmark.INDEX_FINGER_TIP,
        mp_hands.HandLandmark.MIDDLE_FINGER_TIP,
        mp_hands.HandLandmark.RING_FINGER_TIP,
        mp_hands.HandLandmark.PINKY_TIP,
    ]

    # Суставы ниже кончиков (для определения поднят ли палец)
    FINGER_PIPS = [
        mp_hands.HandLandmark.THUMB_IP,
        mp_hands.HandLandmark.INDEX_FINGER_PIP,
        mp_hands.HandLandmark.MIDDLE_FINGER_PIP,
        mp_hands.HandLandmark.RING_FINGER_PIP,
        mp_hands.HandLandmark.PINKY_PIP,
    ]

    def count_fingers(hand_landmarks, handedness):
        """Считает количество поднятых пальцев."""
        fingers_up = []

        # Большой палец — сравниваем по оси X (зависит от руки)
        thumb_tip = hand_landmarks.landmark[FINGER_TIPS[0]]
        thumb_ip = hand_landmarks.landmark[FINGER_PIPS[0]]

        if handedness == "Right":
            fingers_up.append(thumb_tip.x < thumb_ip.x)
        else:
            fingers_up.append(thumb_tip.x > thumb_ip.x)

        # Остальные пальцы — сравниваем по оси Y (кончик выше сустава = поднят)
        for i in range(1, 5):
            tip = hand_landmarks.landmark[FINGER_TIPS[i]]
            pip = hand_landmarks.landmark[FINGER_PIPS[i]]
            fingers_up.append(tip.y < pip.y)

        return fingers_up

    def get_gesture(fingers_up):
        """Определяет жест по поднятым пальцам."""
        total = sum(fingers_up)

        if total == 0:
            return "Кулак"
        if total == 5:
            return "Ладонь"
        if fingers_up == [False, True, False, False, False]:
            return "Указание"
        if fingers_up == [False, True, True, False, False]:
            return "Мир / Victory"
        if fingers_up == [True, False, False, False, True]:
            return "Рок!"
        if fingers_up == [True, True, False, False, False]:
            return "Пистолет"
        if fingers_up == [False, False, False, False, True]:
            return "Мизинец"
        if fingers_up == [True, False, False, False, False]:
            return "Лайк"

        return f"Пальцев: {total}"

    # Захват видео
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Ошибка: не удалось открыть камеру!")
        print("Проверьте подключение веб-камеры.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    print("Камера запущена. Покажите руку!")
    print("Нажмите Q или ESC для выхода.")

    prev_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Ошибка чтения кадра.")
            break

        # Зеркалим для удобства
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape

        # Конвертируем в RGB для MediaPipe
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb)

        # FPS
        curr_time = time.time()
        fps = 1 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 0
        prev_time = curr_time

        cv2.putText(frame, f"FPS: {int(fps)}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        if results.multi_hand_landmarks:
            for idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                # Определяем какая рука
                handedness = results.multi_handedness[idx].classification[0].label
                hand_label = "Правая" if handedness == "Right" else "Левая"
                confidence = results.multi_handedness[idx].classification[0].score

                # Рисуем скелет руки
                mp_draw.draw_landmarks(
                    frame,
                    hand_landmarks,
                    mp_hands.HAND_CONNECTIONS,
                    mp_styles.get_default_hand_landmarks_style(),
                    mp_styles.get_default_hand_connections_style(),
                )

                # Считаем пальцы
                fingers_up = count_fingers(hand_landmarks, handedness)
                gesture = get_gesture(fingers_up)
                total_up = sum(fingers_up)

                # Bounding box руки
                x_coords = [lm.x for lm in hand_landmarks.landmark]
                y_coords = [lm.y for lm in hand_landmarks.landmark]
                x_min = int(min(x_coords) * w) - 20
                y_min = int(min(y_coords) * h) - 20
                x_max = int(max(x_coords) * w) + 20
                y_max = int(max(y_coords) * h) + 20

                # Рамка вокруг руки
                color = (0, 255, 0) if handedness == "Right" else (255, 0, 0)
                cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), color, 2)

                # Информация
                info_y = y_min - 10
                cv2.putText(frame, f"{hand_label} ({confidence:.0%})",
                            (x_min, info_y), cv2.FONT_HERSHEY_SIMPLEX,
                            0.7, color, 2)

                # Жест — внизу рамки
                cv2.putText(frame, gesture,
                            (x_min, y_max + 25), cv2.FONT_HERSHEY_SIMPLEX,
                            0.8, (0, 255, 255), 2)

                # Счётчик пальцев
                cv2.putText(frame, str(total_up),
                            (x_max - 30, y_min + 35), cv2.FONT_HERSHEY_SIMPLEX,
                            1.2, (0, 0, 255), 3)

                # Индикаторы пальцев внизу экрана
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
    hands.close()
    print("Завершено.")


if __name__ == "__main__":
    main()
