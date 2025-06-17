from fastapi import FastAPI, HTTPException
import uvicorn
from datetime import datetime
import threading
from modules.models import SensorData
from modules.database import InfluxDBManager
from typing import Callable

class APIServer:
    def __init__(self, log_callback: Callable = None):
        self.app = FastAPI()
        self.log_callback = log_callback if log_callback else print
        self.db_manager = InfluxDBManager()
        
        # Define API endpoints
        @self.app.post("/sensor-data")
        async def receive_sensor_data(data: SensorData):
            try:
                self.log_callback(f"Received sensor data: {data}")
                
                device_timestamp = None
                if data.timestamp:
                    device_timestamp = datetime.strptime(data.timestamp, "%Y-%m-%dT%H:%M:%SZ")
                
                # Write to InfluxDB
                success = self.db_manager.write_sensor_data(data, device_timestamp)
                
                if success:
                    return {"status": "Success"}
                else:
                    raise Exception("Failed to write to database")
                    
            except Exception as e:
                self.log_callback(f"Error processing sensor data: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
    
    def start(self, host="0.0.0.0", port=8080):
        """Start the FastAPI server in a separate thread"""
        def run_server():
            uvicorn.run(self.app, host=host, port=port)
        
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        return server_thread
