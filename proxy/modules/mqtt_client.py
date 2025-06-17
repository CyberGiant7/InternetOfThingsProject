import paho.mqtt.client as mqtt
from modules.config import MQTT_BROKER, MQTT_PORT, CLIENT_ID, USER, PASSWORD

class MQTTManager:
    def __init__(self, on_connect_callback=None, on_message_callback=None):
        # MQTT Client setup
        self.client = mqtt.Client(CLIENT_ID)
        self.client.username_pw_set(USER, PASSWORD)
        
        # Set callbacks
        if on_connect_callback:
            self.client.on_connect = on_connect_callback
        else:
            self.client.on_connect = self._default_on_connect
            
        if on_message_callback:
            self.client.on_message = on_message_callback
        else:
            self.client.on_message = self._default_on_message
        
        self.connected = False
    
    def connect(self):
        """Connect to the MQTT broker"""
        try:
            self.client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            self.client.loop_start()
            self.connected = True
            return True
        except Exception as e:
            print(f"MQTT connection error: {str(e)}")
            return False
    
    def disconnect(self):
        """Disconnect from the MQTT broker"""
        self.client.loop_stop()
        self.client.disconnect()
        self.connected = False
    
    def publish(self, topic, message):
        """Publish a message to a topic"""
        if not self.connected:
            return False, "Not connected to broker"
        
        result = self.client.publish(topic, message)
        return result[0] == 0, f"Message sent: {topic} -> {message}" if result[0] == 0 else "Failed to send message"
    
    def is_connected(self):
        """Check if the client is connected"""
        return self.connected
    
    def _default_on_connect(self, client, userdata, flags, rc):
        """Default connection callback"""
        if rc == 0:
            print("Connected to MQTT broker")
        else:
            print(f"Connection failed with code {rc}")
    
    def _default_on_message(self, client, userdata, msg):
        """Default message callback"""
        print(f"Message received: {msg.topic} -> {msg.payload.decode()}")
