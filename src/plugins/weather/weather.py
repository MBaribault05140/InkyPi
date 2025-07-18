import requests
from datetime import datetime, timezone
import pytz
import logging
from plugins.base_plugin.base_plugin import BasePlugin

logger = logging.getLogger(__name__)

API_KEY = "29ea29d7-34d4-499c-80a1-3fe18bcdd204"  # <- confirmed as the correct bearer token
STATION_ID = "39534"
AIR_QUALITY_API_KEY = "44927775ca927b99ec49364e9a19023e"

WEATHER_URL = "https://swd.weatherflow.com/swd/rest/better_forecast?station_id={station_id}&units_temp=f&units_wind=mph&units_pressure=mb&units_precip=in&units_distance=mi&api_key={api_key}"
AIR_QUALITY_URL = "http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={api_key}"
CURRENT_WEATHER_URL = "http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=imperial"
STATION_INFO_URL = "https://swd.weatherflow.com/swd/rest/stations?station_id={station_id}&api_key={api_key}"

class Weather(BasePlugin):
    def get_station_observation_data(self, station_id, api_key):
        url = f"https://swd.weatherflow.com/swd/rest/observations/station/{station_id}?units=imperial&api_key={api_key}"
        try:
            response = requests.get(url)
            if response.ok:
                data = response.json()
                obs = data.get("obs", [])
                if obs and isinstance(obs[0], dict):
                    c_to_f = lambda c: round((c * 9 / 5) + 32, 1)
                    return {
                        "air_temperature": c_to_f(obs[0].get("air_temperature", 0)),
                        "feels_like": c_to_f(obs[0].get("feels_like", 0)),
                        "station_pressure": obs[0].get("station_pressure"),
                        "wind_avg": obs[0].get("wind_avg")
                    }
            logger.warning("Failed to retrieve observation data from Tempest.")
        except Exception as e:
            logger.exception("Error fetching station observation data")
        return {}

    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params['style_settings'] = True
        return template_params

    def generate_image(self, settings, device_config, current_dt=None):
        station_id = settings.get("stationId").strip() if settings.get("stationId") else STATION_ID
        api_key = settings.get("bearerToken").strip() if settings.get("bearerToken") else API_KEY
        logger.info(f"Loaded bearerToken from settings: {settings.get('bearerToken')}")
        air_quality_api_key = settings.get("airQualityApiKey").strip() if settings.get("airQualityApiKey") else AIR_QUALITY_API_KEY
        logger.info(f"Using Tempest API Key: {api_key}")
        logger.info(f"Using Air Quality API Key: {air_quality_api_key}")
        weather_data = self.get_weather_data(api_key, station_id)
        lat, lon = self.get_station_coordinates(station_id, api_key)
        if lat is None or lon is None:
            raise RuntimeError("Missing latitude or longitude from Tempest station metadata.")

        aqi_data = self.get_air_quality_data(lat, lon, air_quality_api_key)
        visibility_miles = self.get_current_weather_visibility(lat, lon, air_quality_api_key)

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        timezone_str = device_config.get_config("timezone", default="America/New_York")
        tz = pytz.timezone(timezone_str)
        template_params = {}
        if current_dt:
            aligned_time = current_dt.strftime("%A, %B %d – %-I:%M %p")
            logger.info(f"Using aligned current_dt for timestamp: {aligned_time}")
            template_params["timestamp_override"] = aligned_time
        else:
            now_time = datetime.now(tz).strftime("%A, %B %d – %-I:%M %p")
            logger.info(f"No current_dt provided, using now: {now_time}")
            template_params["timestamp_override"] = now_time
        template_params.update(self.parse_weather_data(weather_data, aqi_data, visibility_miles, tz, current_dt, template_params))
        template_params["custom_location_name"] = settings.get("locationName") or template_params["location"]
        template_params["style"] = settings.get("style", "no-frame")
        template_params["backgroundColor"] = settings.get("backgroundColor", "#000000")
        template_params["textColor"] = settings.get("textColor", "#ffffff")
        template_params["plugin_settings"] = settings

        image = self.render_image(dimensions, "weather.html", "weather.css", template_params)
        if not image:
            raise RuntimeError("Failed to take screenshot, please check logs.")
        return image

    def get_station_coordinates(self, station_id, api_key):
        url = STATION_INFO_URL.format(station_id=station_id, api_key=api_key)
        response = requests.get(url)
        if not response.ok:
            logger.error(f"Failed to retrieve station metadata: {response.status_code} {response.text}")
            return None, None
        try:
            data = response.json()
            stations = data.get("stations", [])
            if stations:
                lat = stations[0].get("latitude")
                lon = stations[0].get("longitude")
                return lat, lon
        except Exception as e:
            logger.exception("Error parsing station metadata JSON")
        return None, None

    def get_weather_data(self, bearer_token, station_id):
        url = WEATHER_URL.format(station_id=station_id, api_key=bearer_token)
        response = requests.get(url)
        if not 200 <= response.status_code < 300:
            logger.error(f"Failed to retrieve weather data: {response.content}")
            raise RuntimeError("Failed to retrieve weather data.")
        return response.json()

    def get_air_quality_data(self, lat, lon, api_key):
        url = AIR_QUALITY_URL.format(lat=lat, lon=lon, api_key=api_key)
        logger.info(f"Calling air quality API: {url}")
        response = requests.get(url)
        logger.info(f"Air quality API raw response: {response.text}")
        if not 200 <= response.status_code < 300:
            logger.error(f"Air Quality API failed. Status: {response.status_code}, Response: {response.text}")
            raise RuntimeError("Failed to retrieve air quality data.")

        try:
            data = response.json()
            if "list" in data and data["list"]:
                return data
            else:
                logger.warning("Air quality data missing 'list' or list is empty.")
                return {"list": [{}]}  # prevents index errors downstream
        except Exception as e:
            logger.exception("Error parsing air quality JSON:")
            return {"list": [{}]}

    def get_current_weather_visibility(self, lat, lon, api_key):
        url = CURRENT_WEATHER_URL.format(lat=lat, lon=lon, api_key=api_key)
        response = requests.get(url)
        if response.ok:
            data = response.json()
            visibility = data.get("visibility")
            if visibility is not None:
                return visibility / 1609.34  # meters to miles
        return 10  # fallback if visibility missing

    def parse_weather_data(self, weather_data, aqi_data, visibility_miles, tz, current_dt=None, template_params=None):
        current = weather_data.get("current_conditions", {})
        daily = weather_data.get("forecast", {}).get("daily", [])
        dt = current_dt if current_dt else datetime.now(tz)
        current_icon = current.get("icon", "default")

        obs_data = self.get_station_observation_data(STATION_ID, API_KEY)
        current_temperature = obs_data.get("air_temperature", current.get("air_temperature", 0))
        feels_like = obs_data.get("feels_like", current.get("feels_like", current_temperature))

        # Use scheduler-aligned timestamp for the current_date label
        data = {
            "current_date": template_params.get("timestamp_override", dt.strftime("%A, %B %d – %-I:%M %p")),
            "location": "Washington, DC",  # fallback name
            "current_day_icon": self.get_plugin_dir(f"icons/{current_icon}.png"),
            "current_temperature": str(round(current_temperature)),
            "feels_like": str(round(feels_like)),
            "temperature_unit": "°F",
            "units": "imperial",
            "forecast": self.parse_forecast(daily, tz),
            "hourly_forecast": self.parse_hourly(weather_data.get("forecast", {}).get("hourly", []), tz),
            "data_points": self.parse_data_points(current, daily, aqi_data, visibility_miles, tz, obs_data)
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

    def parse_data_points(self, current, daily_forecast, aqi_data, visibility_miles, tz, obs_data):
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
        if obs_data.get("wind_avg") is not None:
            data_points.append({
                "label": "Wind",
                "measurement": obs_data["wind_avg"],
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

        if obs_data.get("station_pressure") is not None:
            data_points.append({
                "label": "Pressure",
                "measurement": obs_data["station_pressure"],
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
