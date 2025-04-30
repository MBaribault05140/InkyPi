
import requests
from datetime import datetime, timezone

class WeatherPlugin:
    def __init__(self, api_key, station_id):
        self.api_key = api_key
        self.station_id = station_id

    def get_weather_data(self):
        url = f"https://api.weatherflow.com/sensor_data?station_id={self.station_id}&api_key={self.api_key}"
        response = requests.get(url)
        return response.json()

    def parse_forecast(self, daily_forecast, tz):
        forecast = []
        for day in daily_forecast:
            dt = datetime.fromtimestamp(day.get("day_start_local", 0), tz=timezone.utc).astimezone(tz)
            forecast.append({
                "day": dt.strftime("%a"),
                "high_temp": int(day.get("air_temp_high", 0)),  # Capture high temperature
                "low_temp": int(day.get("air_temp_low", 0)),    # Capture low temperature
                "icon": self.get_plugin_dir(f"icons/{day.get('icon', 'default')}.png")
            })
        return forecast

    def get_plugin_dir(self, icon):
        # This function should map icons correctly from the plugin directory
        return f"/path/to/icons/{icon}"

# Example usage
plugin = WeatherPlugin(api_key="YOUR_API_KEY", station_id="YOUR_STATION_ID")
weather_data = plugin.get_weather_data()
daily_forecast = weather_data["forecast"]["daily"]
forecast = plugin.parse_forecast(daily_forecast, tz=datetime.now().astimezone().tzinfo)
