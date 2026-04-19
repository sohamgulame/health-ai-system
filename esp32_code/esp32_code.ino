#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include "MAX30105.h"
#include "spo2_algorithm.h"

const char* WIFI_SSID = "TP-Link_8114";
const char* WIFI_PASSWORD = "17934602";

const char* SERVER_URL = "http://192.168.0.101:5000/api/health-data";

const int ONE_WIRE_BUS = 4;
const unsigned long POST_INTERVAL_MS = 10000;
const byte RATE_SIZE = 100;

MAX30105 particleSensor;
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature ds18b20(&oneWire);

uint32_t irBuffer[RATE_SIZE];
uint32_t redBuffer[RATE_SIZE];

int32_t spo2 = 0;
int8_t validSPO2 = 0;
int32_t heartRate = 0;
int8_t validHeartRate = 0;
float temperatureC = 0.0;
unsigned long lastPostTime = 0;

bool connectMAX30102() {
  if (!particleSensor.begin(Wire, I2C_SPEED_FAST)) {
    Serial.println("MAX30102 was not found. Check wiring and power.");
    return false;
  }

  particleSensor.setup();
  particleSensor.setPulseAmplitudeRed(0x1F);
  particleSensor.setPulseAmplitudeIR(0x1F);
  particleSensor.setPulseAmplitudeGreen(0);
  return true;
}

void connectToWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to WiFi");

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("WiFi connected");
    Serial.print("ESP32 IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.print("WiFi failed. Status: ");
    Serial.println(WiFi.status());
  }
}

bool capturePulseOximeterData() {
  if (!particleSensor.available()) {
    particleSensor.check();
  }

  Serial.println("Collecting MAX30102 samples...");

  for (byte i = 0; i < RATE_SIZE; i++) {
    while (!particleSensor.available()) {
      particleSensor.check();
      delay(10);
    }

    redBuffer[i] = particleSensor.getRed();
    irBuffer[i] = particleSensor.getIR();
    particleSensor.nextSample();
  }

  maxim_heart_rate_and_oxygen_saturation(
    irBuffer,
    RATE_SIZE,
    redBuffer,
    &spo2,
    &validSPO2,
    &heartRate,
    &validHeartRate
  );

  return validSPO2 == 1 && validHeartRate == 1;
}

float captureTemperature() {
  ds18b20.requestTemperatures();
  float value = ds18b20.getTempCByIndex(0);
  if (value == DEVICE_DISCONNECTED_C) {
    Serial.println("DS18B20 not detected.");
    return NAN;
  }
  return value;
}

void sendHealthReading() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi disconnected. Reconnecting...");
    connectToWiFi();
    if (WiFi.status() != WL_CONNECTED) {
      return;
    }
  }

  bool pulseReady = capturePulseOximeterData();
  temperatureC = captureTemperature();

  if (!pulseReady) {
    Serial.println("Unable to calculate stable SpO2 / heart rate. Adjust finger placement.");
    return;
  }

  if (isnan(temperatureC)) {
    Serial.println("Skipping POST because temperature reading failed.");
    return;
  }

  String payload = "{";
  payload += "\"spo2\":" + String(spo2) + ",";
  payload += "\"heart_rate\":" + String(heartRate) + ",";
  payload += "\"temperature\":" + String(temperatureC, 2);
  payload += "}";

  HTTPClient http;
  http.begin(SERVER_URL);
  http.setTimeout(30000);
  http.addHeader("Content-Type", "application/json");

  int httpResponseCode = http.POST(payload);

  Serial.println("Sending live reading...");
  Serial.print("Payload: ");
  Serial.println(payload);
  Serial.print("HTTP Response code: ");
  Serial.println(httpResponseCode);

  if (httpResponseCode > 0) {
    String response = http.getString();
    Serial.println("Response:");
    Serial.println(response);
  } else {
    Serial.print("POST failed: ");
    Serial.println(http.errorToString(httpResponseCode));
  }

  http.end();
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  Wire.begin();
  ds18b20.begin();

  if (!connectMAX30102()) {
    while (true) {
      delay(1000);
    }
  }

  connectToWiFi();
}

void loop() {
  unsigned long currentTime = millis();
  if (currentTime - lastPostTime >= POST_INTERVAL_MS) {
    lastPostTime = currentTime;
    sendHealthReading();
  }
}

