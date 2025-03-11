import uvicorn
from fastapi import FastAPI, HTTPException
from influxdb_client import InfluxDBClient, Point
from pydantic import BaseModel
from datetime import datetime
import sys
import os

# Aggiungi il percorso della directory data_analytics al path di Python
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data_analytics'))
from performance_evaluation import PerformanceEvaluator

app = FastAPI()


# Modello dati per la richiesta
class SensorData(BaseModel):
    tempIndoor: float
    humIndoor: float
    tempOutdoor: float
    humOutdoor: float
    timestamp: str = None  # Timestamp opzionale per misurare la latenza


# Configurazione InfluxDB (sostituisci con i tuoi dati)
INFLUXDB_URL = "http://localhost:8086"
INFLUXDB_TOKEN = "uHnhErrBaY76NeLUWGjJfHTmooN0FibnAK1GTifGmqAYxRD6cWqVdsvtaQ_PD9G2i9fX9HasvUpXTin-KPiKoQ=="
INFLUXDB_ORG = "ProgettoIot"
INFLUXDB_BUCKET = "ProgettoIot"

# Connessione a InfluxDB
influx_client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
write_api = influx_client.write_api()

# Inizializza il valutatore di prestazioni
performance_evaluator = PerformanceEvaluator()


@app.post("/sensor-data")
async def receive_sensor_data(data: SensorData):
    print(data)
    try:
        # Registra la latenza se è presente un timestamp
        if data.timestamp:
            try:
                device_timestamp = datetime.fromisoformat(data.timestamp)
                latency = performance_evaluator.record_data_latency(device_timestamp)
                print(f"Latenza misurata: {latency:.2f} ms")
            except (ValueError, TypeError) as e:
                print(f"Errore nel calcolo della latenza: {e}")
        
        # Scrivi i dati in InfluxDB
        if data.tempIndoor:
            point_indoor = Point("temperature").tag("location", "indoor").field("value", data.tempIndoor)
            write_api.write(bucket=INFLUXDB_BUCKET, record=point_indoor)
        if data.humIndoor:
            point_indoor = Point("humidity").tag("location", "indoor").field("value", data.humIndoor)
            write_api.write(bucket=INFLUXDB_BUCKET, record=point_indoor)
        if data.tempOutdoor:
            point_outdoor = Point("temperature").tag("location", "outdoor").field("value", data.tempOutdoor)
            write_api.write(bucket=INFLUXDB_BUCKET, record=point_outdoor)
        if data.humOutdoor:
            point_outdoor = Point("humidity").tag("location", "outdoor").field("value", data.humOutdoor)
            write_api.write(bucket=INFLUXDB_BUCKET, record=point_outdoor)

        return {"status": "Data written to InfluxDB", "latency_ms": latency if 'latency' in locals() else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
