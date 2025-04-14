#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>


const char* ssid     = "";
const char* password = "";

WebServer server(80);


#define CAMERA_MODEL_AI_THINKER
#include "camera_pins.h"  


void handleJPG();
void handleJPGStream();
void startCustomCameraServer();

void setup() {
  Serial.begin(115200);
  Serial.setDebugOutput(true);
  Serial.println();

  
  camera_config_t config;
  config.ledc_channel    = LEDC_CHANNEL_0;
  config.ledc_timer      = LEDC_TIMER_0;
  config.pin_d0          = Y2_GPIO_NUM;
  config.pin_d1          = Y3_GPIO_NUM;
  config.pin_d2          = Y4_GPIO_NUM;
  config.pin_d3          = Y5_GPIO_NUM;
  config.pin_d4          = Y6_GPIO_NUM;
  config.pin_d5          = Y7_GPIO_NUM;
  config.pin_d6          = Y8_GPIO_NUM;
  config.pin_d7          = Y9_GPIO_NUM;
  config.pin_xclk        = XCLK_GPIO_NUM;
  config.pin_pclk        = PCLK_GPIO_NUM;
  config.pin_vsync       = VSYNC_GPIO_NUM;
  config.pin_href        = HREF_GPIO_NUM;
  config.pin_sscb_sda    = SIOD_GPIO_NUM;
  config.pin_sscb_scl    = SIOC_GPIO_NUM;
  config.pin_pwdn        = PWDN_GPIO_NUM;
  config.pin_reset       = RESET_GPIO_NUM;
  config.xclk_freq_hz    = 20000000;
  config.pixel_format    = PIXFORMAT_JPEG;
  
  
  if (psramFound()){
    config.frame_size   = FRAMESIZE_UXGA;
    config.jpeg_quality = 10;
    config.fb_count     = 2;
  } else {
    config.frame_size   = FRAMESIZE_SVGA;
    config.jpeg_quality = 12;
    config.fb_count     = 1;
  }
  
  
  esp_err_t err = esp_camera_init(&config);
  if(err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    return;
  }
  
  
  IPAddress local_IP(192, 168, 1, 103);  
  IPAddress gateway(192, 168, 1, 1);       
  IPAddress subnet(255, 255, 255, 0);      
  if (!WiFi.config(local_IP, gateway, subnet)) {
    Serial.println("Errore nella configurazione dell'IP statico.");
  }
  
  
  WiFi.begin(ssid, password);
  Serial.print("Connessione al WiFi");
  while(WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.println("WiFi connesso");
  
  
  startCustomCameraServer();
  
  Serial.print("Camera Stream Ready! Vai a: http:
  Serial.print(WiFi.localIP());
  Serial.println("/");
}

void loop() {
  server.handleClient();
}


void handleJPG() {
  WiFiClient client = server.client();
  String header = "HTTP/1.1 200 OK\r\nContent-Type: image/jpeg\r\n\r\n";
  server.sendContent(header);

  camera_fb_t* fb = esp_camera_fb_get();
  if(!fb) {
    Serial.println("Errore catturando l'immagine");
    return;
  }
  client.write(fb->buf, fb->len);
  esp_camera_fb_return(fb);
}


void handleJPGStream() {
  String header = "HTTP/1.1 200 OK\r\nContent-Type: multipart/x-mixed-replace;boundary=frame\r\n\r\n";
  server.sendContent(header);

  while (1) {
    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Errore catturando l'immagine");
      continue;
    }
    
    String partHeader = "--frame\r\nContent-Type: image/jpeg\r\n\r\n";
    server.sendContent(partHeader);
    server.client().write(fb->buf, fb->len);
    server.sendContent("\r\n");
    esp_camera_fb_return(fb);

    
    if (!server.client().connected()) {
      break;
    }
  }
}


void startCustomCameraServer() {
  
  server.on("/", HTTP_GET, []() {
    server.send(200, "text/html", "<html><body><img src='/stream'></body></html>");
  });
  
  
  server.on("/cam-hi.jpg", HTTP_GET, handleJPG);
  
  
  server.on("/stream", HTTP_GET, handleJPGStream);
  
  server.begin();
  Serial.println("Server HTTP avviato");
}
