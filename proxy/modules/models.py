from pydantic import BaseModel

class SensorData(BaseModel):
    tempIndoor: float
    humIndoor: float
    tempOutdoor: float
    humOutdoor: float
    timestamp: str = None
