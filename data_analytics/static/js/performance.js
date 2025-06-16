// Performance page variables
let currentData = {};

// Update metrics display based on selected horizon
function updateMetricsDisplay() {
    const horizon = document.getElementById("forecast-horizon").value;
    const metrics = currentData.forecast_accuracy?.[horizon];
    
    if (metrics && metrics.mae.length > 0) {
        const lastIndex = metrics.mae.length - 1;
        document.getElementById("mae-value").textContent = metrics.mae[lastIndex].toFixed(2);
        document.getElementById("mse-value").textContent = metrics.mse[lastIndex].toFixed(2);
        document.getElementById("rmse-value").textContent = metrics.rmse[lastIndex].toFixed(2);
    } else {
        document.getElementById("mae-value").textContent = "--";
        document.getElementById("mse-value").textContent = "--";
        document.getElementById("rmse-value").textContent = "--";
    }
    
    // Update chart with selected horizon data
    const data = currentData.forecast_accuracy?.[horizon];
    if (data) {
        updateForecastAccuracyChart(data, horizon);
    }
}

// Fetch performance data from server
async function fetchPerformanceData() {
    try {
        const response = await fetch('/performance-data');
        currentData = await response.json();
        
        // Update metrics for current selected horizon
        updateMetricsDisplay();
        
        // Update latency chart
        console.log(currentData);
        if (currentData.latency) {
            document.getElementById("avg-latency-value").textContent = 
                (currentData.latency.average || 0).toFixed(2);
            
            if (currentData.latency_metrics) {
                updateLatencyChart(currentData.latency_metrics);
            }
        }
    } catch (error) {
        console.error("Error retrieving performance data:", error);
    }
}

// Initialize performance dashboard
function initPerformanceDashboard() {
    // Load initial data
    fetchPerformanceData();
    
    // Set up interval to fetch data every 30 seconds
    setInterval(fetchPerformanceData, 30000);
}

// Run initialization when DOM is ready
document.addEventListener('DOMContentLoaded', initPerformanceDashboard);