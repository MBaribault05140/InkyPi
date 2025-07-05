import requests

def get_weather():
    # Set your station ID and API key
    station_id = "39534"
    api_key = "29ea29d7-34d4-499c-80a1-3fe18bcdd204"
    
    # Construct the API endpoint URL.
    # (Note: This URL is based on Weatherflow’s REST API for observations.
    #  Check https://weatherflow.github.io/SmartWeather/api-docs/ for the latest details.)
    url = f"https://swd.weatherflow.com/swd/rest?command=observations&station_id={station_id}&api_key={api_key}"
    
    response = requests.get(url)
    response.raise_for_status()  # Raise an error for bad responses
    return response.json()

if __name__ == '__main__':
    weather_data = get_weather()
    print(weather_data)
