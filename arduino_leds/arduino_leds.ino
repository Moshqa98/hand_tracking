/*
  Управление 4 светодиодами через ШИМ по данным с Python hand tracking.

  Пины:
    6  — указательный палец
    9  — средний палец
    10 — безымянный палец
    11 — мизинец

  Формат входных данных (Serial, 9600 baud):
    "V1,V2,V3,V4\n"
    где V = 0..255 (0 = палец разогнут/LED выкл, 255 = палец согнут/LED макс)
*/

const int LED_PINS[] = {6, 9, 10, 11};
const int NUM_LEDS = 4;

int pwmValues[4] = {0, 0, 0, 0};

void setup() {
  Serial.begin(9600);
  for (int i = 0; i < NUM_LEDS; i++) {
    pinMode(LED_PINS[i], OUTPUT);
    analogWrite(LED_PINS[i], 0);
  }
}

void loop() {
  if (Serial.available()) {
    String data = Serial.readStringUntil('\n');
    data.trim();

    if (data.length() > 0) {
      int idx = 0;
      int startPos = 0;

      for (int i = 0; i <= data.length() && idx < NUM_LEDS; i++) {
        if (i == data.length() || data.charAt(i) == ',') {
          String val = data.substring(startPos, i);
          int pwm = val.toInt();
          pwm = constrain(pwm, 0, 255);
          pwmValues[idx] = pwm;
          idx++;
          startPos = i + 1;
        }
      }

      // Применяем PWM
      for (int i = 0; i < NUM_LEDS; i++) {
        analogWrite(LED_PINS[i], pwmValues[i]);
      }
    }
  }
}
