import tkinter as tk
from tkinter import ttk, messagebox
import paho.mqtt.client as mqtt
from fastapi import FastAPI, HTTPException
from influxdb_client import InfluxDBClient, Point
from pydantic import BaseModel
import uvicorn
from datetime import datetime
import threading
import sys
import os

# MQTT Configuration
# MQTT_BROKER = "localhost"
MQTT_BROKER = "192.168.4.157"
MQTT_PORT = 1883
CLIENT_ID = "DataProxyClient"
USER = "arduino"
PASSWORD = "progettoiot"

# InfluxDB Configuration
INFLUXDB_URL = "http://localhost:8086"
INFLUXDB_TOKEN = "uHnhErrBaY76NeLUWGjJfHTmooN0FibnAK1GTifGmqAYxRD6cWqVdsvtaQ_PD9G2i9fX9HasvUpXTin-KPiKoQ=="
INFLUXDB_ORG = "ProgettoIot"
INFLUXDB_BUCKET = "ProgettoIot"


# Predefined commands
COMMANDS = {
    "Turn On HVAC": {"topic": "hvac/control", "message": "start"},
    "Turn Off HVAC": {"topic": "hvac/control", "message": "stop"},
    "Turn On LED": {"topic": "hvac/led", "message": "on"},
    "Turn Off LED": {"topic": "hvac/led", "message": "off"},
}

class SensorData(BaseModel):
    tempIndoor: float
    humIndoor: float
    tempOutdoor: float
    humOutdoor: float
    timestamp: str = None


# Modify MQTTClientGUI class
class MQTTClientGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("MQTT Client & Data Proxy")
        self.root.geometry("800x600")
        
        # Initialize FastAPI and InfluxDB
        self.app = FastAPI()
        self.influx_client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
        self.write_api = self.influx_client.write_api()
        
        # MQTT Client setup
        self.client = mqtt.Client(CLIENT_ID)
        self.client.username_pw_set(USER, PASSWORD)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        # GUI Elements
        self.create_widgets()
        
        # Connection status
        self.connected = False
        
        # Start FastAPI server immediately
        self.start_fastapi()
        self.log_message("Data Proxy server started on port 8080")

    def toggle_connection(self):
        if not self.connected:
            try:
                self.client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
                self.client.loop_start()
                self.conn_button.configure(text="Disconnect")
                self.send_button.state(['!disabled'])
                self.status_label.configure(text="Connected to broker")
                self.connected = True
            except Exception as e:
                messagebox.showerror("Connection Error", str(e))
        else:
            self.client.loop_stop()
            self.client.disconnect()
            self.conn_button.configure(text="Connect")
            self.send_button.state(['disabled'])
            self.status_label.configure(text="Disconnected")
            self.connected = False

    def create_widgets(self):
        # Connection frame
        conn_frame = ttk.LabelFrame(self.root, text="Connection", padding="5")
        conn_frame.pack(fill="x", padx=5, pady=5)
        
        self.conn_button = ttk.Button(conn_frame, text="Connect", command=self.toggle_connection)
        self.conn_button.pack(fill="x")
        
        # Commands frame
        cmd_frame = ttk.LabelFrame(self.root, text="Quick Commands", padding="5")
        cmd_frame.pack(fill="x", padx=5, pady=5)
        
        # Add Sampling Rate control
        sampling_frame = ttk.Frame(cmd_frame)
        sampling_frame.pack(fill="x", pady=2)
        
        ttk.Label(sampling_frame, text="Sampling Rate (ms):").pack(side="left")
        self.sampling_entry = ttk.Entry(sampling_frame, width=10)
        self.sampling_entry.pack(side="left", padx=5)
        self.sampling_entry.insert(0, "1000")
        
        ttk.Button(sampling_frame, text="Set Rate", 
                  command=self.send_sampling_rate).pack(side="left")
        
        # Existing command buttons
        for cmd_name, cmd_data in COMMANDS.items():
            btn = ttk.Button(cmd_frame, text=cmd_name,
                           command=lambda t=cmd_data["topic"], m=cmd_data["message"]: 
                           self.send_predefined_message(t, m))
            btn.pack(fill="x", pady=2)
            
        # Custom Message frame
        msg_frame = ttk.LabelFrame(self.root, text="Custom Message", padding="5")
        msg_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Topic
        ttk.Label(msg_frame, text="Topic:").pack(fill="x")
        self.topic_entry = ttk.Entry(msg_frame)
        self.topic_entry.pack(fill="x", pady=(0, 5))
        self.topic_entry.insert(0, "hvac/control")
        
        # Message
        ttk.Label(msg_frame, text="Message:").pack(fill="x")
        self.message_entry = ttk.Entry(msg_frame)
        self.message_entry.pack(fill="x", pady=(0, 5))
        
        # Send button
        self.send_button = ttk.Button(msg_frame, text="Send Custom Message", command=self.send_message)
        self.send_button.pack(fill="x")
        self.send_button.state(['disabled'])
        
        # Add Data Proxy Log frame before Status frame
        log_frame = ttk.LabelFrame(self.root, text="Data Proxy Log", padding="5")
        log_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Add Text widget for log with scrollbar (read-only)
        self.log_text = tk.Text(log_frame, height=10, width=50, state='disabled')
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Status frame
        status_frame = ttk.LabelFrame(self.root, text="Status", padding="5")
        status_frame.pack(fill="x", padx=5, pady=5)
        
        self.status_label = ttk.Label(status_frame, text="Disconnected")
        self.status_label.pack(fill="x")

    def send_predefined_message(self, topic, message):
        if not self.connected:
            messagebox.showwarning("Warning", "Not connected to broker")
            return
            
        result = self.client.publish(topic, message)
        if result[0] == 0:
            self.status_label.configure(text=f"Message sent: {topic} -> {message}")
        else:
            messagebox.showerror("Error", "Failed to send message")

    def start_fastapi(self):
        @self.app.post("/sensor-data")
        async def receive_sensor_data(data: SensorData):
            self.log_message(f"Received sensor data: {data}")
            try:
                if data.timestamp:
                    device_timestamp = datetime.fromisoformat(data.timestamp)
                    self.log_message(f"Timestamp: {device_timestamp}")
                
                # Write to InfluxDB
                for location, temp, hum in [("indoor", data.tempIndoor, data.humIndoor),
                                         ("outdoor", data.tempOutdoor, data.humOutdoor)]:
                    self.write_api.write(
                        bucket=INFLUXDB_BUCKET,
                        record=[
                            Point("temperature").tag("location", location).field("value", temp),
                            Point("humidity").tag("location", location).field("value", hum)
                        ]
                    )
                
                return {"status": "Success"}
            except Exception as e:
                self.log_message(f"Error: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

        # Run FastAPI in a separate thread
        def run_fastapi():
            uvicorn.run(self.app, host="0.0.0.0", port=8080)
        
        threading.Thread(target=run_fastapi, daemon=True).start()

    def log_message(self, message):
        self.log_text.configure(state='normal')
        self.log_text.insert(tk.END, f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state='disabled')

    def send_message(self):
        if not self.connected:
            messagebox.showwarning("Warning", "Not connected to broker")
            return
            
        topic = self.topic_entry.get().strip()
        message = self.message_entry.get().strip()
        
        if not topic or not message:
            messagebox.showwarning("Warning", "Topic and message cannot be empty")
            return
            
        result = self.client.publish(topic, message)
        if result[0] == 0:
            self.status_label.configure(text=f"Message sent: {topic} -> {message}")
            self.message_entry.delete(0, tk.END)
        else:
            messagebox.showerror("Error", "Failed to send message")

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT broker")
        else:
            print(f"Connection failed with code {rc}")

    def on_message(self, client, userdata, msg):
        print(f"Message received: {msg.topic} -> {msg.payload.decode()}")

    def send_sampling_rate(self):
        if not self.connected:
            messagebox.showwarning("Warning", "Not connected to broker")
            return
        
        try:
            rate = int(self.sampling_entry.get().strip())
            if rate <= 0:
                raise ValueError("Sampling rate must be positive")
            
            result = self.client.publish("hvac/sampling_rate", str(rate))
            if result[0] == 0:
                self.status_label.configure(text=f"Sampling rate set to: {rate} ms")
            else:
                messagebox.showerror("Error", "Failed to send sampling rate")
        except ValueError as e:
            messagebox.showerror("Error", "Please enter a valid positive number")

if __name__ == "__main__":
    root = tk.Tk()
    app = MQTTClientGUI(root)
    root.mainloop()