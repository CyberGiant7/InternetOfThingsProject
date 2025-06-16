// Global chart variables
let temperatureChart;
let apiComparisonChart;

// Performance page chart variables
let forecastAccuracyChart;
let latencyChart;

// Initialize temperature chart
function initTemperatureChart(data) {
    const ctx = document.getElementById("temperatureChart").getContext("2d");
    
    temperatureChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: data.timestamps.concat(data.prediction_timestamps),
            datasets: [
                {
                    label: "Indoor Temperature",
                    data: data.indoor.concat(new Array(data.predictions.length).fill(null)),
                    borderColor: "blue",
                    fill: false
                },
                {
                    label: "Outdoor Temperature",
                    data: data.outdoor.concat(new Array(data.predictions.length).fill(null)),
                    borderColor: "green",
                    fill: false
                },
                {
                    label: "Forecast (30 min)",
                    data: new Array(data.indoor.length).fill(null).concat(data.predictions),
                    borderColor: "red",
                    borderDash: [5, 5],
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Time'
                    }
                },
                y: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Temperature (°C)'
                    }
                }
            },
            plugins: {
                legend: {
                    position: 'top'
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            }
        }
    });
}

// Update temperature chart with new data
function updateChart(data) {
    if (!temperatureChart) {
        initTemperatureChart(data);
    } else {
        temperatureChart.data.labels = data.timestamps.concat(data.prediction_timestamps);
        temperatureChart.data.datasets[0].data = data.indoor.concat(new Array(data.predictions.length).fill(null));
        temperatureChart.data.datasets[1].data = data.outdoor.concat(new Array(data.predictions.length).fill(null));
        temperatureChart.data.datasets[2].data = new Array(data.indoor.length).fill(null).concat(data.predictions);
        temperatureChart.update();
    }
}

// Initialize API comparison chart
function initApiComparisonChart() {
    const apiCtx = document.getElementById('apiComparisonChart').getContext('2d');
    
    apiComparisonChart = new Chart(apiCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Outdoor Sensor',
                    data: [],
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 2,
                    fill: false
                },
                {
                    label: 'Weather API',
                    data: [],
                    borderColor: 'rgba(255, 99, 132, 1)',
                    borderWidth: 2,
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Time'
                    }
                },
                y: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Temperature (°C)'
                    }
                }
            },
            plugins: {
                legend: {
                    position: 'top'
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            }
        }
    });
}

// Update API comparison chart with nested api_data structure
function updateApiComparisonChart(data) {
    // Create chart if it doesn't exist yet
    if (!apiComparisonChart) {
        initApiComparisonChart();
    }
    
    // Access the nested api_data structure
    const apiData = data.api_data;
    
    if (!apiData || !apiData.temp_api || apiData.temp_api.length === 0) {
        console.log('No API data available yet');
        return;
    }
    
    // Extract API temperature data and timestamps
    let apiTemps = [];
    let outdoorTemps = [];
    let timestamps = [];
    
    apiTemps = apiData.temp_api;
    outdoorTemps = apiData.temp_outdoor;
    timestamps = apiData.timestamp;
    
    
    // Limit to last 30 points for readability
    const maxPoints = 30;
    if (apiTemps.length > maxPoints) {
        apiTemps = apiTemps.slice(-maxPoints);
        outdoorTemps = outdoorTemps.slice(-maxPoints);
        timestamps = timestamps.slice(-maxPoints);
    }
    
    // Update chart with API and outdoor sensor data
    apiComparisonChart.data.labels = timestamps;
    apiComparisonChart.data.datasets[0].data = outdoorTemps;
    apiComparisonChart.data.datasets[1].data = apiTemps;
    apiComparisonChart.update();
}

// Initialize forecast accuracy chart
function initForecastAccuracyChart(data, horizon) {
    const ctx = document.getElementById("forecastAccuracyChart").getContext("2d");
    
    forecastAccuracyChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: data.timestamps,
            datasets: [
                {
                    label: "MAE",
                    data: data.mae,
                    borderColor: "blue",
                    backgroundColor: "rgba(0, 0, 255, 0.1)",
                    fill: false,
                    tension: 0.1
                },
                {
                    label: "RMSE",
                    data: data.rmse,
                    borderColor: "red",
                    backgroundColor: "rgba(255, 0, 0, 0.1)",
                    fill: false,
                    tension: 0.1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: "Date/Time"
                    }
                },
                y: {
                    beginAtZero: true,
                    display: true,
                    title: {
                        display: true,
                        text: "Error (°C)"
                    }
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: `Forecast Accuracy Over Time (${horizon})`
                },
                legend: {
                    position: 'top'
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            }
        },
    });
}

// Update forecast accuracy chart
function updateForecastAccuracyChart(data, horizon) {
    if (!data || !data.timestamps || data.timestamps.length === 0) {
        return;
    }
    
    if (!forecastAccuracyChart) {
        initForecastAccuracyChart(data, horizon);
    } else {
        forecastAccuracyChart.data.labels = data.timestamps;
        forecastAccuracyChart.data.datasets[0].data = data.mae;
        forecastAccuracyChart.data.datasets[1].data = data.rmse;
        forecastAccuracyChart.options.plugins.title.text = 
            `Forecast Accuracy Over Time (${horizon})`;
        forecastAccuracyChart.update();
    }
}

// Initialize latency chart
function initLatencyChart(data) {
    const ctx = document.getElementById("latencyChart").getContext("2d");
    
    latencyChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: data.timestamps,
            datasets: [
                {
                    label: "Latency",
                    data: data.latency_ms,
                    borderColor: "green",
                    backgroundColor: "rgba(0, 255, 0, 0.1)",
                    fill: false,
                    tension: 0.1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    ticks: {
                        maxTicksLimit: 10
                    },
                    title: {
                        display: true,
                        text: "Date/Time"
                    }
                },
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: "Latency (ms)"
                    }
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: "Network Latency Over Time"
                },
                legend: {
                    position: 'top'
                }
            }
        }
    });
}

// Update latency chart
function updateLatencyChart(data) {
    if (!data || !data.timestamps || data.timestamps.length === 0) {
        return;
    }
    
    if (!latencyChart) {
        initLatencyChart(data);
    } else {
        latencyChart.data.labels = data.timestamps;
        latencyChart.data.datasets[0].data = data.latency_ms;
        latencyChart.update();
    }
}