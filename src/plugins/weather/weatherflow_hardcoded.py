
import requests
from datetime import datetime, timezone
import pytz
import logging
from plugins.base_plugin.base_plugin import BasePlugin

logger = logging.getLogger(__name__)

# Hardcoded API key and station ID
API_KEY = "29ea29d7-34d4-499c-80a1-3fe18bcdd204"
STATION_ID = "39534"

WEATHER_URL = "https://swd.weatherflow.com/swd/rest/better_forecast?station_id={station_id}&units_temp=c&units_wind=mps&units_pressure=mb&units_precip=mm&units_distance=km&api_key={api_key}"

class Weather(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params['style_settings'] = True
        return template_params

    def generate_image(self, settings, device_config):
        weather_data = self.get_weather_data(API_KEY, STATION_ID)

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        timezone_str = device_config.get_config("timezone", default="America/New_York")
        tz = pytz.timezone(timezone_str)
        template_params = self.parse_weather_data(weather_data, tz)
        template_params["plugin_settings"] = settings

        image = self.render_image(dimensions, "weather.html", "weather.css", template_params)
        if not image:
            raise RuntimeError("Failed to take screenshot, please check logs.")
        return image

    def get_weather_data(self, api_key, station_id):
        url = WEATHER_URL.format(station_id=station_id, api_key=api_key)
        response = requests.get(url)
        if not 200 <= response.status_code < 300:
            logger.error(f"Failed to retrieve weather data: {response.content}")
            raise RuntimeError("Failed to retrieve weather data.")
        return response.json()

    def parse_weather_data(self, weather_data, tz):
        current = weather_data.get("current_conditions", {})
        dt = datetime.fromtimestamp(current.get("time"), tz=timezone.utc).astimezone(tz)
        current_icon = current.get("icon")

        data = {
            "current_date": dt.strftime("%A, %B %d – %-I:%M %p"),
            "location": f"Station {weather_data.get('station_id', 'Unknown')}",
            "current_day_icon": self.get_plugin_dir(f"icons/{current_icon}.png"),
            "current_temperature": str(round(current.get("air_temperature"))),
            "feels_like": str(round(current.get("feels_like", current.get("air_temperature")))),
            "temperature_unit": "°C",
            "units": "metric",
            "forecast": self.parse_forecast(weather_data.get("forecast", {}).get("daily", []), tz),
            "hourly_forecast": self.parse_hourly(weather_data.get("forecast", {}).get("hourly", []), tz)
        }

        return data

    def parse_forecast(self, daily_forecast, tz):
        forecast = []
        for day in daily_forecast[1:]:
            dt = datetime.fromtimestamp(day.get("day_start_local"), tz=timezone.utc).astimezone(tz)
            day_forecast = {
                "day": dt.strftime("%a"),
                "high": int(day.get("air_temp_high")),
                "low": int(day.get("air_temp_low")),
                "icon": self.get_plugin_dir(f"icons/{day.get('icon')}.png")
            }
            forecast.append(day_forecast)
        return forecast

    def parse_hourly(self, hourly_forecast, tz):
        hourly = []
        for hour in hourly_forecast[:24]:
            dt = datetime.fromtimestamp(hour.get("time"), tz=timezone.utc).astimezone(tz)
            hour_forecast = {
                "time": dt.strftime("%-I %p"),
                "temperature": int(hour.get("air_temperature")),
                "precipitation": hour.get("precip_probability", 0)
            }
            hourly.append(hour_forecast)
        return hourly
