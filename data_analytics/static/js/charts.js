// Global chart variables
let temperatureChart;
let apiComparisonChart;

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
                    ticks: {
                        maxTicksLimit: 10
                    }
                },
                y: {
                    beginAtZero: false
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
    
    // Handle nested arrays in the api_data structure
    if (Array.isArray(apiData.temp_api[0])) {
        // Flatten nested arrays if needed
        apiData.temp_api.forEach(arr => {
            if (arr && arr.length > 0) {
                apiTemps = apiTemps.concat(arr);
            }
        });
        
        apiData.temp_outdoor.forEach(arr => {
            if (arr && arr.length > 0) {
                outdoorTemps = outdoorTemps.concat(arr);
            }
        });
        
        apiData.timestamp.forEach(arr => {
            if (arr && arr.length > 0) {
                timestamps = timestamps.concat(arr);
            }
        });
    } else {
        // Data is already flat
        apiTemps = apiData.temp_api;
        outdoorTemps = apiData.temp_outdoor;
        timestamps = apiData.timestamp;
    }
    
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