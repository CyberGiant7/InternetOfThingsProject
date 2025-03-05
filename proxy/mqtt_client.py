import time
import paho.mqtt.client as mqtt

# Configurazioni MQTT
MQTT_BROKER = "192.168.4.157"  # Indirizzo del broker MQTT
MQTT_PORT = 1883  # Porta del broker (default: 1883)
CLIENT_ID = "DataProxyClient"  # Identificativo del client
USER = "arduino"
PASSWORD = "progettoiot"


class MQTTClient:
    def __init__(self, broker=MQTT_BROKER, port=MQTT_PORT):
        self.broker = broker
        self.port = port
        self.client = mqtt.Client(CLIENT_ID)
        self.client.username_pw_set(USER, PASSWORD)
        # Callback per la connessione e la ricezione dei messaggi
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, rc):
        """Callback eseguita al momento della connessione al broker."""
        if rc == 0:
            print("Connesso con successo al broker MQTT.")
            # Se necessario, iscriversi a topic per ricevere messaggi
            # self.client.subscribe("hvac/status")
        else:
            print(f"Connessione fallita con codice: {rc}")

    def on_message(self, client, userdata, msg):
        """Callback eseguita alla ricezione di un messaggio."""
        print(f"Messaggio ricevuto su topic '{msg.topic}': {msg.payload.decode()}")

    def connect(self):
        """Connessione al broker MQTT e avvio del loop in background."""
        self.client.connect(self.broker, self.port, keepalive=60)
        self.client.loop_start()  # Avvia il loop in background

    def disconnect(self):
        """Termina il loop e disconnette il client dal broker."""
        self.client.loop_stop()
        self.client.disconnect()

    def publish_command(self, topic, message):
        """
        Invia un comando sul topic specificato.
        topic: ad esempio "hvac/control" o "hvac/led"
        message: ad esempio "start", "stop", "on", "off"
        """
        result = self.client.publish(topic, message)
        status = result[0]
        if status == 0:
            print(f"Inviato '{message}' sul topic '{topic}'.")
        else:
            print(f"Errore nell'invio del messaggio sul topic '{topic}'.")


if __name__ == "__main__":
    mqtt_client = MQTTClient(MQTT_BROKER, MQTT_PORT)
    mqtt_client.connect()

    try:
        while True:
            user_input = input("Inserisci comando nel formato '<topic> <messaggio>' (oppure 'exit' per uscire): ")
            if user_input.strip().lower() == "exit":
                break
            parts = user_input.strip().split()
            if len(parts) < 2:
                print("Formato non valido. Esempio: hvac/control start")
                continue
            topic = parts[0]
            message = " ".join(parts[1:])
            mqtt_client.publish_command(topic, message)
    except KeyboardInterrupt:
        print("\nInterruzione da tastiera.")

    mqtt_client.disconnect()
    print("Client MQTT disconnesso.")
