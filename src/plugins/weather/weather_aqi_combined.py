
import requests
from datetime import datetime, timezone
import pytz
import logging
from plugins.base_plugin.base_plugin import BasePlugin

logger = logging.getLogger(__name__)

# WeatherFlow API info
API_KEY = "29ea29d7-34d4-499c-80a1-3fe18bcdd204"
STATION_ID = "39534"

# OpenWeatherMap AQI info
LAT = "38.8951"
LON = "-77.0364"
AIR_QUALITY_API_KEY = "YOUR_OPENWEATHERMAP_API_KEY"
AIR_QUALITY_URL = "http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={api_key}"

WEATHER_URL = "https://swd.weatherflow.com/swd/rest/better_forecast?station_id={station_id}&units_temp=f&units_wind=mph&units_pressure=mb&units_precip=in&units_distance=mi&api_key={api_key}"

class Weather(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params['style_settings'] = True
        return template_params

    def generate_image(self, settings, device_config):
        weather_data = self.get_weather_data(API_KEY, STATION_ID)
        aqi_data = self.get_air_quality_data(AIR_QUALITY_API_KEY)

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        timezone_str = device_config.get_config("timezone", default="America/New_York")
        tz = pytz.timezone(timezone_str)
        template_params = self.parse_weather_data(weather_data, aqi_data, tz)
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

    def get_air_quality_data(self, api_key):
        url = AIR_QUALITY_URL.format(lat=LAT, lon=LON, api_key=api_key)
        response = requests.get(url)
        if not 200 <= response.status_code < 300:
            logger.error(f"Failed to retrieve air quality data: {response.content}")
            raise RuntimeError("Failed to retrieve air quality data.")
        return response.json()

    def parse_weather_data(self, weather_data, aqi_data, tz):
        current = weather_data.get("current_conditions", {})
        dt = datetime.fromtimestamp(current.get("time"), tz=timezone.utc).astimezone(tz)
        current_icon = current.get("icon")

        data = {
            "current_date": dt.strftime("%A, %B %d – %-I:%M %p"),
            "location": "Washington, DC",
            "current_day_icon": self.get_plugin_dir(f"icons/{current_icon}.png"),
            "current_temperature": str(round(current.get("air_temperature"))),
            "feels_like": str(round(current.get("feels_like", current.get("air_temperature")))),
            "temperature_unit": "°F",
            "units": "imperial",
            "forecast": self.parse_forecast(weather_data.get("forecast", {}).get("daily", []), tz),
            "hourly_forecast": self.parse_hourly(weather_data.get("forecast", {}).get("hourly", []), tz),
            "data_points": self.parse_data_points(current, aqi_data, tz)
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

    def parse_data_points(self, current, aqi_data, tz):
        data_points = []

        if "sunrise" in current:
            sunrise_dt = datetime.fromtimestamp(current["sunrise"], tz=timezone.utc).astimezone(tz)
            data_points.append({
                "label": "Sunrise",
                "measurement": sunrise_dt.strftime('%I:%M').lstrip("0"),
                "unit": sunrise_dt.strftime('%p'),
                "icon": self.get_plugin_dir('icons/sunrise.png')
            })

        if "sunset" in current:
            sunset_dt = datetime.fromtimestamp(current["sunset"], tz=timezone.utc).astimezone(tz)
            data_points.append({
                "label": "Sunset",
                "measurement": sunset_dt.strftime('%I:%M').lstrip("0"),
                "unit": sunset_dt.strftime('%p'),
                "icon": self.get_plugin_dir('icons/sunset.png')
            })

        if "wind_speed" in current:
            data_points.append({
                "label": "Wind",
                "measurement": current["wind_speed"],
                "unit": "mph",
                "icon": self.get_plugin_dir('icons/wind.png')
            })

        if "humidity" in current:
            data_points.append({
                "label": "Humidity",
                "measurement": current["humidity"],
                "unit": "%",
                "icon": self.get_plugin_dir('icons/humidity.png')
            })

        if "sea_level_pressure" in current:
            data_points.append({
                "label": "Pressure",
                "measurement": current["sea_level_pressure"],
                "unit": "mb",
                "icon": self.get_plugin_dir('icons/pressure.png')
            })

        if "uv" in current:
            data_points.append({
                "label": "UV Index",
                "measurement": current["uv"],
                "unit": '',
                "icon": self.get_plugin_dir('icons/uvi.png')
            })

        if "visibility" in current:
            data_points.append({
                "label": "Visibility",
                "measurement": round(current["visibility"] / 1000, 1),
                "unit": "mi",
                "icon": self.get_plugin_dir('icons/visibility.png')
            })

        aqi = aqi_data.get('list', [])[0].get("main", {}).get("aqi", 0)
        aqi_labels = ["Good", "Fair", "Moderate", "Poor", "Very Poor"]
        if aqi:
            data_points.append({
                "label": "Air Quality",
                "measurement": aqi,
                "unit": aqi_labels[aqi - 1],
                "icon": self.get_plugin_dir('icons/aqi.png')
            })

        return data_points
