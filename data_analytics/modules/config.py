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
    "forecast_horizon": 60
}