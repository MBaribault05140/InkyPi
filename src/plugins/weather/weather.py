import requests
from datetime import datetime, timezone
import pytz
import logging
from plugins.base_plugin.base_plugin import BasePlugin

logger = logging.getLogger(__name__)

API_KEY = "29ea29d7-34d4-499c-80a1-3fe18bcdd204"
STATION_ID = "39534"
AIR_QUALITY_API_KEY = "44927775ca927b99ec49364e9a19023e"

WEATHER_URL = "https://swd.weatherflow.com/swd/rest/better_forecast?station_id={station_id}&units_temp=f&units_wind=mph&units_pressure=mb&units_precip=in&units_distance=mi&api_key={api_key}"
AIR_QUALITY_URL = "http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={api_key}"
CURRENT_WEATHER_URL = "http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=imperial"

class Weather(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params['style_settings'] = True
        return template_params

    def generate_image(self, settings, device_config):
        station_id = settings.get("stationId", STATION_ID)
        weather_data = self.get_weather_data(API_KEY, station_id)
        location = weather_data.get("location", {})
        lat = location.get("latitude")
        lon = location.get("longitude")

        aqi_data = self.get_air_quality_data(lat, lon, AIR_QUALITY_API_KEY)
        visibility_miles = self.get_current_weather_visibility(lat, lon, AIR_QUALITY_API_KEY)

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        timezone_str = device_config.get_config("timezone", default="America/New_York")
        tz = pytz.timezone(timezone_str)
        template_params = self.parse_weather_data(weather_data, aqi_data, visibility_miles, tz)
        template_params["custom_location_name"] = settings.get("locationName") or template_params["location"]
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

    def get_air_quality_data(self, lat, lon, api_key):
        url = AIR_QUALITY_URL.format(lat=lat, lon=lon, api_key=api_key)
        response = requests.get(url)
        if not 200 <= response.status_code < 300:
            logger.error(f"Failed to retrieve air quality data: {response.content}")
            raise RuntimeError("Failed to retrieve air quality data.")
        return response.json()

    def get_current_weather_visibility(self, lat, lon, api_key):
        url = CURRENT_WEATHER_URL.format(lat=lat, lon=lon, api_key=api_key)
        response = requests.get(url)
        if response.ok:
            data = response.json()
            visibility = data.get("visibility")
            if visibility is not None:
                return visibility / 1609.34  # meters to miles
        return 10  # fallback if visibility missing

    def parse_weather_data(self, weather_data, aqi_data, visibility_miles, tz):
        current = weather_data.get("current_conditions", {})
        daily = weather_data.get("forecast", {}).get("daily", [])
        dt = datetime.fromtimestamp(current.get("time", 0), tz=timezone.utc).astimezone(tz)
        current_icon = current.get("icon", "default")

        data = {
            "current_date": dt.strftime("%A, %B %d – %-I:%M %p"),
            "location": "Washington, DC",  # fallback name
            "current_day_icon": self.get_plugin_dir(f"icons/{current_icon}.png"),
            "current_temperature": str(round(current.get("air_temperature", 0))),
            "feels_like": str(round(current.get("feels_like", current.get("air_temperature", 0)))),
            "temperature_unit": "°F",
            "units": "imperial",
            "forecast": self.parse_forecast(daily, tz),
            "hourly_forecast": self.parse_hourly(weather_data.get("forecast", {}).get("hourly", []), tz),
            "data_points": self.parse_data_points(current, daily, aqi_data, visibility_miles, tz)
        }

        # Extract High/Low Temperature from the forecast and include it in the data
        if daily:
            today = daily[0]  # Today's forecast (first item in the daily list)
            high = round(today.get("air_temp_high", 0))
            low = round(today.get("air_temp_low", 0))
            data["high_low_temperature"] = f"High: {high}°F / Low: {low}°F"  # Add this to the data dictionary

        return data

    def parse_forecast(self, daily_forecast, tz):
        forecast = []
        for day in daily_forecast[1:]:
            dt = datetime.fromtimestamp(day.get("day_start_local", 0), tz=timezone.utc).astimezone(tz)
            forecast.append({
                "day": dt.strftime("%a"),
                "high": int(day.get("air_temp_high", 0)),
                "low": int(day.get("air_temp_low", 0)),
                "icon": self.get_plugin_dir(f"icons/{day.get('icon', 'default')}.png")
            })
        return forecast

    def parse_hourly(self, hourly_forecast, tz):
        hourly = []
        for hour in hourly_forecast[:24]:
            dt = datetime.fromtimestamp(hour.get("time", 0), tz=timezone.utc).astimezone(tz)
            hourly.append({
                "time": dt.strftime("%-I %p"),
                "temperature": int(hour.get("air_temperature", 0)),
                "precipitation": hour.get("precip_probability", 0)
            })
        return hourly

    def parse_data_points(self, current, daily_forecast, aqi_data, visibility_miles, tz):
        data_points = []

        if daily_forecast:
            today = daily_forecast[0]
            if today.get("sunrise"):
                sunrise = datetime.fromtimestamp(today["sunrise"], tz=timezone.utc).astimezone(tz)
                data_points.append({
                    "label": "Sunrise",
                    "measurement": sunrise.strftime('%I:%M').lstrip("0"),
                    "unit": sunrise.strftime('%p'),
                    "icon": self.get_plugin_dir('icons/sunrise.png')
                })
            if today.get("sunset"):
                sunset = datetime.fromtimestamp(today["sunset"], tz=timezone.utc).astimezone(tz)
                data_points.append({
                    "label": "Sunset",
                    "measurement": sunset.strftime('%I:%M').lstrip("0"),
                    "unit": sunset.strftime('%p'),
                    "icon": self.get_plugin_dir('icons/sunset.png')
                })

        # Add data points for wind, humidity, pressure, UV, visibility, and air quality
        if current.get("wind_avg") is not None:
            data_points.append({
                "label": "Wind",
                "measurement": current["wind_avg"],
                "unit": "mph",
                "icon": self.get_plugin_dir('icons/wind.png')
            })

        if current.get("relative_humidity") is not None:
            data_points.append({
                "label": "Humidity",
                "measurement": current["relative_humidity"],
                "unit": "%",
                "icon": self.get_plugin_dir('icons/humidity.png')
            })

        if current.get("station_pressure") is not None:
            data_points.append({
                "label": "Pressure",
                "measurement": current["station_pressure"],
                "unit": "mb",
                "icon": self.get_plugin_dir('icons/pressure.png')
            })

        if current.get("uv") is not None:
            data_points.append({
                "label": "UV Index",
                "measurement": current["uv"],
                "unit": '',
                "icon": self.get_plugin_dir('icons/uvi.png')
            })

        if visibility_miles is not None:
            data_points.append({
                "label": "Visibility",
                "measurement": round(visibility_miles, 1),
                "unit": "mi",
                "icon": self.get_plugin_dir('icons/visibility.png')
            })

        aqi = aqi_data.get('list', [])[0].get("main", {}).get("aqi", 0)
        aqi_labels = ["Good", "Fair", "Moderate", "Poor", "Very Poor"]
        if aqi:
            data_points.append({
                "label": "Air Quality",
                "measurement": aqi_labels[aqi - 1],
                "unit": "",
                "icon": self.get_plugin_dir('icons/aqi.png')
            })

        return data_points
