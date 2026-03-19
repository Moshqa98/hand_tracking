/*
  Управление 4 светодиодами через ШИМ по данным с Python hand tracking.

  Формат входных данных (Serial, 9600 baud):
    "V1,V2,V3,V4\n"
    где V = 0..255 (0 = палец разогнут/LED выкл, 255 = палец согнут/LED макс)
*/

// Пин каждого светодиода отдельно
const int LED_INDEX  = 6;   // Указательный палец
const int LED_MIDDLE = 9;   // Средний палец
const int LED_RING   = 10;  // Безымянный палец
const int LED_PINKY  = 11;  // Мизинец

int pwmIndex  = 0;
int pwmMiddle = 0;
int pwmRing   = 0;
int pwmPinky  = 0;

void setup() {
  Serial.begin(9600);

  pinMode(LED_INDEX, OUTPUT);
  pinMode(LED_MIDDLE, OUTPUT);
  pinMode(LED_RING, OUTPUT);
  pinMode(LED_PINKY, OUTPUT);

  analogWrite(LED_INDEX, 0);
  analogWrite(LED_MIDDLE, 0);
  analogWrite(LED_RING, 0);
  analogWrite(LED_PINKY, 0);
}

void loop() {
  if (Serial.available()) {
    String data = Serial.readStringUntil('\n');
    data.trim();

    if (data.length() > 0) {
      // Парсим 4 значения через запятую
      int comma1 = data.indexOf(',');
      int comma2 = data.indexOf(',', comma1 + 1);
      int comma3 = data.indexOf(',', comma2 + 1);

      if (comma1 > 0 && comma2 > 0 && comma3 > 0) {
        pwmIndex  = constrain(data.substring(0, comma1).toInt(), 0, 255);
        pwmMiddle = constrain(data.substring(comma1 + 1, comma2).toInt(), 0, 255);
        pwmRing   = constrain(data.substring(comma2 + 1, comma3).toInt(), 0, 255);
        pwmPinky  = constrain(data.substring(comma3 + 1).toInt(), 0, 255);

        // Записываем PWM на каждый пин отдельно
        analogWrite(LED_INDEX, pwmIndex);
        analogWrite(LED_MIDDLE, pwmMiddle);
        analogWrite(LED_RING, pwmRing);
        analogWrite(LED_PINKY, pwmPinky);
      }
    }
  }
}
