#include <Wire.h>
#include <BH1750.h>
#include <HTTPClient.h>
#include <WiFi.h>

#define SOIL_PIN 34
#define RELAY_PIN 25

const char* ssid="Telecom casa_EXT";
const char* password="40166575";
const char* server="https://ismaelecarbo.duckdns.org";

BH1750 lightMeter;

void setup(){
  Serial.begin(115200);
  delay(10);
  WiFi.begin(ssid,password);
  Serial.print("connecting to wifi...");
  while(WiFi.status()!=WL_CONNECTED){
    delay(500);
    Serial.print(".");
  }

  Serial.print(" connected");

  //bh1750 connection
  Wire.begin(21,22);
  if(!lightMeter.begin(BH1750::CONTINUOUS_HIGH_RES_MODE)){
    Serial.print("1750 error");
    while(1);
  }

  //relay status
  pinMode(RELAY_PIN,OUTPUT);
  digitalWrite(RELAY_PIN,LOW); //off
}


void loop(){

  int soilRaw = analogRead(SOIL_PIN);
  float soilPercent = map(soilRaw, 3500, 1400, 0, 100); //mapping soil data
  soilPercent = constrain(soilPercent, 0, 100);
  float lux = lightMeter.readLightLevel();

  Serial.print("Soil: ");
  Serial.print(soilPercent);
  Serial.print("Light: ");
  Serial.print(lux);


  //sending datas to server
    if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(String(server) + "/api/irrigation_data");
    http.addHeader("Content-Type", "application/json");
    String body = "{\"moisture\":";
           body += String(soilPercent,1);
           body += ",\"light\":";
           body += String(lux,1);
           body += "}";
    int httpCode = http.POST(body);
    Serial.printf("POST /api/irrigation_data → %d\n", httpCode);
    http.end();
  } else {
    Serial.println("WiFi non connesso, salto POST");
  }


  //checking soil and lux datas
  if(soilPercent<50.0&&lux<30){
    Serial.print("pump activated");
    digitalWrite(RELAY_PIN,LOW); //relay on
  }else{
    Serial.print("pump disactivated");
    digitalWrite(RELAY_PIN,HIGH);
  }

  delay(5000);
}