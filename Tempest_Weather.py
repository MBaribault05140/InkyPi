import requests

def get_weather():
    # Your station details
    station_id = "39534"
    api_key = "29ea29d7-34d4-499c-80a1-3fe18bcdd204"
    url = f"https://swd.weatherflow.com/swd/rest/observations/stn/{station_id}?api_key={api_key}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise error for HTTP issues
        return response.json()
    except requests.exceptions.RequestException as e:
        print("Error fetching weather data:", e)
        return None

if __name__ == "__main__":
    data = get_weather()
    print(data)
