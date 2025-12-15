/*
  CW Interface Controlada por PC
  Autor: Lucas (Adaptado para Protocolo Serial)
*/

const int RELAY_PIN = 8;
int wpm = 20;       // Velocidade inicial padrao
int UNIT = 60;      // Sera calculado no setup

struct MorseMap { char c; const char* pattern; };

MorseMap morseTable[] = {
  { 'A', ".-" }, { 'B', "-..." }, { 'C', "-.-." }, { 'D', "-.." },
  { 'E', "." }, { 'F', "..-." }, { 'G', "--." }, { 'H', "...." },
  { 'I', ".." }, { 'J', ".---" }, { 'K', "-.-" }, { 'L', ".-.." },
  { 'M', "--" }, { 'N', "-." }, { 'O', "---" }, { 'P', ".--." },
  { 'Q', "--.-" }, { 'R', ".-." }, { 'S', "..." }, { 'T', "-" },
  { 'U', "..-" }, { 'V', "...-" }, { 'W', ".--" }, { 'X', "-..-" },
  { 'Y', "-.--" }, { 'Z', "--.." },
  { '0', "-----" }, { '1', ".----" }, { '2', "..---" }, { '3', "...--" },
  { '4', "....-" }, { '5', "....." }, { '6', "-...." }, { '7', "--..." },
  { '8', "---.." }, { '9', "----." },
  { '.', ".-.-.-" }, { ',', "--..--" }, { '?', "..--.." }, { '/', "-..-." }, { '=', "-...-" }
};

const int MORSE_TABLE_SIZE = sizeof(morseTable) / sizeof(MorseMap);

void relayOn() { digitalWrite(RELAY_PIN, LOW); }
void relayOff() { digitalWrite(RELAY_PIN, HIGH); }

// Recalcula o tempo da unidade baseado no WPM
void updateSpeed(int newWpm) {
  if (newWpm > 0) {
    wpm = newWpm;
    UNIT = 1200 / wpm;
    Serial.print("INFO: Velocidade ajustada para ");
    Serial.print(wpm);
    Serial.println(" WPM");
  }
}

void sendDit() { relayOn(); delay(UNIT); relayOff(); delay(UNIT); }
void sendDah() { relayOn(); delay(3 * UNIT); relayOff(); delay(UNIT); }
void letterSpace() { delay(2 * UNIT); }
void wordSpace() { delay(6 * UNIT); }

const char* getMorsePattern(char c) {
  if (c >= 'a' && c <= 'z') c = c - 'a' + 'A';
  for (int i = 0; i < MORSE_TABLE_SIZE; i++) {
    if (morseTable[i].c == c) return morseTable[i].pattern;
  }
  return NULL;
}

void sendMorseString(String text) {
  int len = text.length();
  for (int i = 0; i < len; i++) {
    char c = text.charAt(i);
    if (c == ' ') { wordSpace(); continue; }
    const char* pattern = getMorsePattern(c);
    if (pattern == NULL) continue;
    
    for (int j = 0; pattern[j] != '\0'; j++) {
      if (pattern[j] == '.') sendDit();
      else if (pattern[j] == '-') sendDah();
    }
    if (i < len - 1 && text.charAt(i + 1) != ' ') letterSpace();
  }
}

void setup() {
  pinMode(RELAY_PIN, OUTPUT);
  relayOff();
  Serial.begin(9600);
  updateSpeed(20); // Define velocidade inicial
}

void loop() {
  if (Serial.available() > 0) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() == 0) return;

    // PROTOCOLO: Se começar com "/wpm", é comando de configuração
    if (line.startsWith("/wpm")) {
      String valStr = line.substring(5); // Pega o numero depois de "/wpm "
      updateSpeed(valStr.toInt());
    } 
    else {
      // Caso contrário, é texto para transmitir
      Serial.print("TX: ");
      Serial.println(line);
      sendMorseString(line);
      Serial.println("DONE");
    }
  }
}