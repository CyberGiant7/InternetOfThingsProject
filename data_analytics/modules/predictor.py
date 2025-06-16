from pmdarima import auto_arima
import pandas as pd
from datetime import timedelta
import numpy as np
from .config import ANALYSIS_CONFIG

class TemperaturePredictor:
    def __init__(self):
        self.threshold = ANALYSIS_CONFIG["threshold"]
        self.forecast_horizon = ANALYSIS_CONFIG["forecast_horizon"]
        self.measure_every_seconds = ANALYSIS_CONFIG["measure_every_seconds"]

    def predict(self, df: pd.DataFrame, hvac_active=False):
        """
        Generate temperature predictions and check for potential energy waste.
        Only generates alerts if HVAC is active.
        
        Args:
            df: DataFrame with temperature data
            hvac_active: Boolean indicating if HVAC is currently active
            
        Returns:
            Dictionary with predictions and alert status
        """
        if df.empty:
            return None
        
        df.dropna(inplace=True)
        indoor_series = df['indoor']
        outdoor_series = df['outdoor']

        try:
            auto_model = auto_arima(
                indoor_series,
                exogenous=outdoor_series,
                seasonal=False,
                error_action='ignore',
                suppress_warnings=True,
                stepwise=True
            )

            exog_forecast = np.array([outdoor_series.iloc[-1]] * self.forecast_horizon).reshape(-1, 1)
            forecast = auto_model.predict(n_periods=self.forecast_horizon, X=exog_forecast)
            
            last_time = df.index[-1]
            future_timestamps = [
                last_time + timedelta(seconds=self.measure_every_seconds * (i + 1)) 
                for i in range(self.forecast_horizon)
            ]
            
            # Calculate if there's a potential energy waste
            potential_waste = any(abs(pred - indoor_series.iloc[-1]) > self.threshold for pred in forecast)
            
            # Only set alert to True if HVAC is active AND there's potential waste
            if hvac_active and potential_waste:
                alert = "True"
            else:
                alert = "False"

            return {
                "timestamps": df.index.strftime('%Y-%m-%d %H:%M:%S').tolist(),
                "indoor": indoor_series.tolist(),
                "outdoor": outdoor_series.tolist(),
                "predictions": forecast.tolist(),
                "prediction_timestamps": [t.strftime('%Y-%m-%d %H:%M:%S') for t in future_timestamps],
                "alert": alert,
                "hvac_active": hvac_active  # Include HVAC status in the return data
            }
        except Exception as e:
            print(f"Error during prediction: {e}")
            return None