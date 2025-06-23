import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from datetime import datetime
from modules.mqtt_client import MQTTManager
from modules.api_server import APIServer
from modules.database import InfluxDBManager
from modules.config import COMMANDS

class MQTTClientGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("MQTT Client & Data Proxy")
        self.root.geometry("800x600")
        
        # Initialize components
        self.mqtt_manager = MQTTManager(
            on_connect_callback=self.on_connect,
            on_message_callback=self.on_message
        )
        self.db_manager = InfluxDBManager()
        
        # GUI Elements
        self.create_widgets()
        
        # Start FastAPI server immediately
        self.api_server = APIServer(log_callback=self.log_message)
        self.api_server.start()
        self.log_message("Data Proxy server started on port 8080")
        
        # Start alarm checking thread
        self.alarm_check_thread = threading.Thread(target=self.check_alarms, daemon=True)
        self.alarm_check_thread.start()

    def toggle_connection(self):
        if not self.mqtt_manager.is_connected():
            try:
                if self.mqtt_manager.connect():
                    self.conn_button.configure(text="Disconnect")
                    self.send_button.state(['!disabled'])
                    self.status_label.configure(text="Connected to broker")
                else:
                    raise Exception("Failed to connect")
            except Exception as e:
                messagebox.showerror("Connection Error", str(e))
        else:
            self.mqtt_manager.disconnect()
            self.conn_button.configure(text="Connect")
            self.send_button.state(['disabled'])
            self.status_label.configure(text="Disconnected")

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
        
        # Add buttons for predefined commands
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
        if not self.mqtt_manager.is_connected():
            messagebox.showwarning("Warning", "Not connected to broker")
            return
            
        success, message = self.mqtt_manager.publish(topic, message)
        if success:
            self.status_label.configure(text=message)
        else:
            messagebox.showerror("Error", "Failed to send message")

    def log_message(self, message):
        self.log_text.configure(state='normal')
        self.log_text.insert(tk.END, f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state='disabled')

    def send_message(self):
        if not self.mqtt_manager.is_connected():
            messagebox.showwarning("Warning", "Not connected to broker")
            return
            
        topic = self.topic_entry.get().strip()
        message = self.message_entry.get().strip()
        
        if not topic or not message:
            messagebox.showwarning("Warning", "Topic and message cannot be empty")
            return
            
        success, status = self.mqtt_manager.publish(topic, message)
        if success:
            self.status_label.configure(text=status)
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
        if not self.mqtt_manager.is_connected():
            messagebox.showwarning("Warning", "Not connected to broker")
            return
        
        try:
            rate = int(self.sampling_entry.get().strip())
            if rate <= 0:
                raise ValueError("Sampling rate must be positive")
            
            success, message = self.mqtt_manager.publish("hvac/sampling_rate", str(rate))
            if success:
                self.status_label.configure(text=f"Sampling rate set to: {rate} ms")
            else:
                messagebox.showerror("Error", "Failed to send sampling rate")
        except ValueError as e:
            messagebox.showerror("Error", "Please enter a valid positive number")
            
    def check_alarms(self):
        """Check for recent alarms every 10 seconds and control LED"""
        while True:
            if self.mqtt_manager.is_connected():
                try:
                    has_alarms = self.db_manager.check_recent_alarms()
                    
                    # Send MQTT message to control LED
                    led_state = "on" if has_alarms else "off"
                    self.mqtt_manager.publish("hvac/led", led_state)
                    self.log_message(f"LED control: {led_state} (based on alarms)")
                except Exception as e:
                    self.log_message(f"Error checking alarms: {str(e)}")
            
            time.sleep(10)
