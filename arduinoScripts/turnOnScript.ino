#include <ESP8266WiFi.h>
#include <WiFiClientSecure.h>
#include <UniversalTelegramBot.h>

const char* ssid = "";
const char* password = "";

const char* botToken = "";  
const int powerPin = D2; 

WiFiClientSecure client;
UniversalTelegramBot bot(botToken, client);

unsigned long lastCheck = 0;
const unsigned long interval = 3000;

void setup() {
  pinMode(powerPin, OUTPUT);
  digitalWrite(powerPin, HIGH);

  Serial.begin(115200);
  WiFi.begin(ssid, password);

  client.setInsecure(); 

  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connessione al WiFi...");
  }

  Serial.println("WiFi connesso!");
}

void loop() {
  if (millis() - lastCheck > interval) {
    int numNewMessages = bot.getUpdates(bot.last_message_received + 1);

    while (numNewMessages) {
      for (int i = 0; i < numNewMessages; i++) {
        String msg = bot.messages[i].text;
        Serial.println("Messaggio ricevuto: " + msg);

        if (msg == "/accendi") {
          digitalWrite(powerPin, LOW);
          delay(300);
          digitalWrite(powerPin, HIGH);
          bot.sendMessage(bot.messages[i].chat_id, "✅ Raspberry acceso!", "");
        }
      }
      numNewMessages = bot.getUpdates(bot.last_message_received + 1);
    }

    lastCheck = millis();
  }
}
