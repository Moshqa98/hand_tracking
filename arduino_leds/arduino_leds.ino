/*
  Управление 4 светодиодами по данным с Python hand tracking.
  Палец загнут — светодиод горит. Разогнут — выключен.

  Формат входных данных (Serial, 9600 baud):
    "V1,V2,V3,V4\n"
    где V = 0 (выкл) или 1 (вкл)
*/

const int LED_INDEX  = 6;   // Указательный палец
const int LED_MIDDLE = 9;   // Средний палец
const int LED_RING   = 10;  // Безымянный палец
const int LED_PINKY  = 11;  // Мизинец

void setup() {
  Serial.begin(9600);

  pinMode(LED_INDEX, OUTPUT);
  pinMode(LED_MIDDLE, OUTPUT);
  pinMode(LED_RING, OUTPUT);
  pinMode(LED_PINKY, OUTPUT);

  digitalWrite(LED_INDEX, LOW);
  digitalWrite(LED_MIDDLE, LOW);
  digitalWrite(LED_RING, LOW);
  digitalWrite(LED_PINKY, LOW);
}

void loop() {
  if (Serial.available()) {
    String data = Serial.readStringUntil('\n');
    data.trim();

    if (data.length() > 0) {
      int comma1 = data.indexOf(',');
      int comma2 = data.indexOf(',', comma1 + 1);
      int comma3 = data.indexOf(',', comma2 + 1);

      if (comma1 > 0 && comma2 > 0 && comma3 > 0) {
        int valIndex  = data.substring(0, comma1).toInt();
        int valMiddle = data.substring(comma1 + 1, comma2).toInt();
        int valRing   = data.substring(comma2 + 1, comma3).toInt();
        int valPinky  = data.substring(comma3 + 1).toInt();

        digitalWrite(LED_INDEX,  valIndex  ? HIGH : LOW);
        digitalWrite(LED_MIDDLE, valMiddle ? HIGH : LOW);
        digitalWrite(LED_RING,   valRing   ? HIGH : LOW);
        digitalWrite(LED_PINKY,  valPinky  ? HIGH : LOW);
      }
    }
  }
}
