#include <WiFi.h>
#include <PubSubClient.h>
#include <HTTPClient.h>
#include "DHT.h"

// Definizioni per i sensori
#define DHTPIN_INDOOR 13    // Pin del sensore interno
#define DHTPIN_OUTDOOR 25   // Pin del sensore esterno
#define DHTTYPE_INDOOR DHT22      // Tipo di sensore
#define DHTTYPE_OUTDOOR DHT22 
DHT dhtIndoor(DHTPIN_INDOOR, DHTTYPE_INDOOR);
DHT dhtOutdoor(DHTPIN_OUTDOOR, DHTTYPE_OUTDOOR);

// Definizione LED per segnalare allarmi
#define LED_PIN 2

// Configurazione WiFi
const char* ssid = "Wifi";
const char* password = "passwordo";

// Configurazione server HTTP
const char* server_url = "http://192.168.137.167:8080/sensor-data";

// Configurazione MQTT
const char* mqtt_server = "192.168.137.167"; // Sostituisci con l'IP del broker MQTT
const char* mqtt_username = "arduino";  // Inserisci il tuo username MQTT
const char* mqtt_password = "progettoiot";  // Inserisci la tua password MQTT
WiFiClient espClient;
PubSubClient client(espClient);

// Variabili globali
bool acquisitionActive = true;
int samplingInterval = 5000; // Intervallo di campionamento (5 secondi)

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  // Inizializza WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connessione WiFi...");
  }
  Serial.println("WiFi connesso");

  // Inizializza MQTT
  client.setServer(mqtt_server, 1883);
  client.setCallback(mqttCallback);
  reconnectMQTT();

  // Inizializza i sensori
  dhtIndoor.begin();
  dhtOutdoor.begin();
}

void loop() {
  if (!client.connected()) {
    reconnectMQTT();
  }
  client.loop();

  if (acquisitionActive) {
    // Indoor
    float tempIndoor = dhtIndoor.readTemperature();
    Serial.println("Temp indoor: "+ String(tempIndoor));
    float humIndoor = dhtIndoor.readHumidity();
    Serial.println("Hum indoor: "+ String(humIndoor));

    // Outdoor
    float tempOutdoor = dhtOutdoor.readTemperature();
    Serial.println("Temp outdoor: "+ String(tempOutdoor));
    float humOutdoor = dhtOutdoor.readHumidity();
    Serial.println("Hum outdoor: "+ String(humOutdoor));

    //if (!isnan(tempIndoor) && !isnan(tempOutdoor)) {
    sendSensorData(tempIndoor, humIndoor, tempOutdoor, humOutdoor);
    //}
  }
  delay(samplingInterval);
}

void sendSensorData(float tempIndoor, float humIndoor, float tempOutdoor, float humOutdoor) {
  HTTPClient http;
  http.begin(server_url);
  http.addHeader("Content-Type", "application/json");

  String payload = "{\"tempIndoor\": " + String(tempIndoor) + ", \"humIndoor\": " + String(humIndoor) + ", \"tempOutdoor\": " + String(tempOutdoor) + ", \"humOutdoor\": " + String(humOutdoor)+ "}";
  int httpResponseCode = http.POST(payload);
  http.end();

  Serial.print("Dati inviati: ");
  Serial.println(payload);
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String message;
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }

  if (String(topic) == "hvac/control") {
    if (message == "start") {
      Serial.println("Ricevuto hvac/control start");
      acquisitionActive = true;
    } else if (message == "stop") {
      Serial.println("Ricevuto hvac/control stop");
      acquisitionActive = false;
    }
  }
  
  if (String(topic) == "hvac/led") {
    if (message == "on") {
      Serial.println("Ricevuto hvac/led on");
      digitalWrite(LED_PIN, HIGH);
    } else if (message == "off") {
      Serial.println("Ricevuto hvac/led on");
      digitalWrite(LED_PIN, LOW);
    }
  }
}

void reconnectMQTT() {
  while (!client.connected()) {
    Serial.println("Connessione al broker MQTT...");
    // Connetti utilizzando username e password
    if (client.connect("ESP32Client", mqtt_username, mqtt_password)) {
      Serial.println("Connesso a MQTT");
      client.subscribe("hvac/control");
      Serial.println("Sottoscritto a hvac/control");
      client.subscribe("hvac/led");
      Serial.println("Sottoscritto a hvac/led");
    } else {
      Serial.print("Connessione fallita, rc=");
      Serial.print(client.state());
      Serial.println(" Riprovo tra 5 secondi...");
      delay(5000);
    }
  }
}
