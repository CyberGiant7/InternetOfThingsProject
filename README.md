# Internet of Things (IoT) HVAC Monitoring System

A comprehensive IoT solution for monitoring and controlling HVAC (Heating, Ventilation, and Air Conditioning) systems with data analytics capabilities, visualization, and remote control functionality.

## Project Overview

This project implements an end-to-end IoT solution with the following components:

- **Firmware**: Arduino-compatible code running on IoT devices that collect temperature and humidity data
- **Data Proxy**: A bridge between IoT devices and analytics system using MQTT protocol
- **Data Analytics**: Processing, visualization, and predictive analytics for HVAC performance
- **Grafana**: Data visualization dashboards for system monitoring

## Directory Structure

- **firmware/**: Contains Arduino code for IoT devices
- **proxy/**: MQTT broker and data relay system
- **data_analytics/**: Data processing, API, and web dashboard
- **grafana/**: Grafana dashboard configurations

## Requirements

- Python 3.10+
- MQTT Broker (e.g., Mosquitto)
- InfluxDB
- Arduino IDE (for firmware deployment)
- Grafana (for visualization dashboards)

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/CyberGiant7/InternetOfThingsProject.git
   cd InternetOfThingsProject
   ```

2. Install required Python packages:

   ```bash
   pip install -r requirements.txt
   ```

3. Configure the system:
   - Update MQTT broker settings in `proxy/modules/config.py`
   - Configure InfluxDB connection in both proxy and data_analytics modules
   - Set up the `proxy/.env.example` and `data_analytics/.env.example` environment variables if needed and rename them to `.env`
   - Set up Grafana with the provided configuration files in the `grafana/` directory

## Components

### Firmware

The firmware component is designed to run on Arduino-compatible hardware. It:

- Collects temperature and humidity data from sensors
- Sends data to the MQTT broker
- Responds to control commands (start/stop HVAC, LED controls)

To deploy:

1. Open the `firmware/main/main.ino` file in Arduino IDE
2. Configure WiFi and MQTT settings
3. Upload to your device

### Data Proxy

A bridge between IoT devices and the analytics system:

- Exposes REST API endpoints to receive sensor data
- Stores data in InfluxDB for persistence
- Subscribes to MQTT topics to send messages to the microcontroller
- Provides a GUI for monitoring and controlling devices

To run:

```bash
cd proxy
python data_proxy.py
```

### Data Analytics

Processes and analyzes the collected data:

- Web dashboard for visualizing HVAC performance metrics
- Performance evaluation and prediction algorithms
- REST API endpoints for data access
- Telegram bot integration for manually set the HVAC system state

To run:

```bash
cd data_analytics
python app.py
```

To start the Telegram bot:

```bash
cd data_analytics
python bot_runner.py
```

### Grafana

Contains configuration files for Grafana dashboards:

- Visualizes real-time and historical HVAC data
- Performance metrics dashboard
- Alerting and notification configurations

To set up Grafana:

1. Install Grafana on your system
2. Import the provided dashboard JSON files from the `grafana/` directory
3. Configure data sources to connect to InfluxDB
4. Start Grafana server and access the dashboard at `http://localhost:3000`

## API Endpoints

### Data Proxy API

- `POST /sensor-data`: Receives sensor data from devices

### Data Analytics API

- `GET /data`: Retrieves processed data
- `GET /performance-data`: Gets system performance metrics

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

Distributed under the MIT License. See `LICENSE` for more information.

## Acknowledgments

- This project was developed as part of an IoT course offered by the University of Bologna (UNIBO)
- Built with Python, MQTT, and InfluxDB
- Visualization powered by Grafana
