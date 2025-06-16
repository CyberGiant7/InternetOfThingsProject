async function fetchData() {
    try {
        const response = await fetch('/data');
        const data = await response.json();

        // Update temperature displays
        document.getElementById("indoor").textContent = 
            data.indoor.length > 0 ? data.indoor[data.indoor.length - 1].toFixed(2) : "--";
        document.getElementById("outdoor").textContent = 
            data.outdoor.length > 0 ? data.outdoor[data.outdoor.length - 1].toFixed(2) : "--";

        // Update alert display
        if (data.alert === "True") {
            document.getElementById("alert").style.display = "block";
        } else {
            document.getElementById("alert").style.display = "none";
        }
        
        const hvacStatus = data.hvac_active;            
        const hvacStatusCard = document.getElementById('hvac-status');
        const hvacIndicator = document.getElementById('hvac-indicator');
        const hvacText = document.getElementById('hvac-text');
        
        if (hvacStatus) {
            hvacStatusCard.className = 'stat-card hvac active';
            hvacIndicator.textContent = '🔥';
            hvacText.textContent = 'ON';
        } else {
            hvacStatusCard.className = 'stat-card hvac inactive';
            hvacIndicator.textContent = '❄️';
            hvacText.textContent = 'OFF';
        }

        // Update all charts
        updateChart(data);
        updateApiComparisonChart(data);
    } catch (error) {
        console.error("Error fetching data:", error);
    }
}

// Initialize everything when the page loads
function initDashboard() {
    // Start fetching data when the page loads
    fetchData();
    // Set up interval to fetch data every 10 seconds
    setInterval(fetchData, 10000);
}

// Run initialization when DOM is ready
document.addEventListener('DOMContentLoaded', initDashboard);