# Database configurations
INFLUXDB_CONFIG = {
    "url": "http://localhost:8086",
    "token": "uHnhErrBaY76NeLUWGjJfHTmooN0FibnAK1GTifGmqAYxRD6cWqVdsvtaQ_PD9G2i9fX9HasvUpXTin-KPiKoQ==",
    "org": "ProgettoIot",
    "bucket": "ProgettoIot"
}

# Analysis configurations
ANALYSIS_CONFIG = {
    "threshold": 1.0,  # Differenza di temperatura per considerare uno spreco
    "measure_every_seconds": 30,
    "forecast_horizon": 60 # 30 minuti
}

WEATHER_API_CONFIG = {
    "api_key": "f685eee7a5d4db075e4da74bc7f3dccc",
    "city": "Bologna",
    "country_code": "IT",
    "units": "metric"  # metric for Celsius
}
    
    
    