from pmdarima import auto_arima  # Automatic ARIMA model selection for time series forecasting
import pandas as pd
from datetime import timedelta
import numpy as np
from .config import ANALYSIS_CONFIG

class TemperaturePredictor:
    """
    Machine Learning temperature prediction system for IoT energy waste detection.
    
    This class implements an ARIMA-based forecasting model that:
    - Predicts future indoor temperatures using historical sensor data
    - Incorporates outdoor temperature as an exogenous variable
    - Detects potential energy waste scenarios
    - Generates alerts only when HVAC system is active
    - Provides configurable prediction horizons and thresholds
    """
    
    def __init__(self):
        """
        Initialize the temperature predictor with configuration parameters.
        
        Loads configuration settings for:
        - Energy waste detection threshold
        - Prediction time horizon (how far into the future to predict)
        - Data sampling interval for time series processing
        """
        # Temperature difference threshold for energy waste detection (degrees Celsius)
        self.threshold = ANALYSIS_CONFIG["threshold"]
        
        # Number of future time steps to predict
        self.forecast_horizon = ANALYSIS_CONFIG["forecast_horizon"]
        
        # Time interval between sensor measurements (seconds)
        self.measure_every_seconds = ANALYSIS_CONFIG["measure_every_seconds"]

    def predict(self, df: pd.DataFrame, hvac_active=False):
        """
        Generate temperature predictions and check for potential energy waste.
        Only generates alerts if HVAC is active.
        
        Args:
            df (pd.DataFrame): Time-indexed DataFrame with 'indoor' and 'outdoor' temperature columns
            hvac_active (bool): Boolean indicating if HVAC system is currently active
            
        Returns:
            dict: Comprehensive prediction results containing:
                - timestamps: Historical sensor reading timestamps
                - indoor: Historical indoor temperature values
                - outdoor: Historical outdoor temperature values
                - predictions: Future temperature predictions
                - prediction_timestamps: Timestamps for future predictions
                - alert: Energy waste alert status ("True" or "False")
                - hvac_active: Current HVAC system status
            None: If prediction fails due to insufficient data or errors
            
        This method implements the core prediction logic:
        1. Validates input data availability
        2. Builds ARIMA model with outdoor temperature as exogenous variable
        3. Generates multi-step ahead forecasts
        4. Evaluates energy waste potential
        5. Triggers alerts only when HVAC is running
        """
        # Validate input data - return None if DataFrame is empty
        if df.empty:
            print("No data available for prediction")
            return None
        
        # Remove any rows with missing values to ensure clean data for modeling
        df.dropna(inplace=True)
        
        # Extract indoor and outdoor temperature series from DataFrame
        indoor_series = df['indoor']    # Target variable for prediction
        outdoor_series = df['outdoor']  # Exogenous variable (external factor)

        try:
            # Build automatic ARIMA model for temperature forecasting
            # auto_arima automatically selects optimal ARIMA parameters (p,d,q)
            auto_model = auto_arima(
                indoor_series,              # Target time series (indoor temperature)
                exogenous=outdoor_series,   # External variable (outdoor temperature influences indoor)
                seasonal=False,             # Disable seasonal decomposition (short-term predictions)
                error_action='ignore',      # Continue processing despite minor errors
                suppress_warnings=True,     # Reduce console output for cleaner logs
                stepwise=True              # Use stepwise algorithm for faster parameter selection
            )

            # Prepare exogenous data for forecasting
            # Assume outdoor temperature remains constant at last observed value
            # Reshape to 2D array format required by ARIMA model
            exog_forecast = np.array([outdoor_series.iloc[-1]] * self.forecast_horizon).reshape(-1, 1)
            
            # Generate multi-step ahead temperature predictions
            forecast = auto_model.predict(
                n_periods=self.forecast_horizon,  # Number of future time steps
                X=exog_forecast                   # Exogenous variables for prediction period
            )
            
            # Generate timestamps for future predictions
            last_time = df.index[-1]  # Get the most recent timestamp from historical data
            future_timestamps = [
                # Calculate future timestamps based on measurement interval
                last_time + timedelta(seconds=self.measure_every_seconds * (i + 1)) 
                for i in range(self.forecast_horizon)
            ]
            
            # Energy waste detection algorithm
            # Check if any predicted temperature deviates significantly from current temperature
            current_indoor_temp = indoor_series.iloc[-1]  # Most recent indoor temperature
            potential_waste = any(
                abs(pred - current_indoor_temp) > self.threshold 
                for pred in forecast
            )
            
            # Alert logic: Only trigger alerts when HVAC is active AND waste is detected
            # This prevents false alarms when system is not consuming energy
            if hvac_active and potential_waste:
                alert = "True"   # Energy waste detected with active HVAC
                print(f"Energy waste alert: Temperature deviation > {self.threshold}°C with HVAC active")
            else:
                alert = "False"  # No alert (either no waste or HVAC inactive)
                if potential_waste and not hvac_active:
                    print(f"Temperature deviation detected but HVAC is inactive - no alert")

            # Prepare comprehensive response with all prediction data
            return {
                # Historical data for visualization and context
                "timestamps": df.index.strftime('%Y-%m-%d %H:%M:%S').tolist(),
                "indoor": indoor_series.tolist(),
                "outdoor": outdoor_series.tolist(),
                
                # Prediction results
                "predictions": forecast.tolist(),
                "prediction_timestamps": [t.strftime('%Y-%m-%d %H:%M:%S') for t in future_timestamps],
                
                # Alert and system status information
                "alert": alert,
                "hvac_active": hvac_active  # Include HVAC status for frontend display
            }
            
        except Exception as e:
            # Handle any errors during model building or prediction
            print(f"Error during prediction: {e}")
            print(f"Data shape: {df.shape}, Date range: {df.index.min()} to {df.index.max()}")
            return None