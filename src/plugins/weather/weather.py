import requests
from flask import Blueprint, render_template, request, redirect, url_for, flash
from .render import parse_api_response  # Adjust according to your repo structure
from ..utils import load_plugin_settings, save_plugin_settings

weather_bp = Blueprint('weather', __name__, template_folder='render')

@weather_bp.route('/weather/settings', methods=['GET', 'POST'])
def settings():
    # Load existing settings
    settings = load_plugin_settings('weather')

    if request.method == 'POST':
        form = request.form
        # Core settings
        settings['api_key']  = form.get('api_key', '').strip()
        settings['latitude'] = form.get('latitude', '').strip()
        settings['longitude'] = form.get('longitude', '').strip()
        settings['units']     = form.get('units', 'metric')
        # New: manual display override
        settings['manual_location_name'] = form.get('manual_location_name', '').strip()

        # Persist settings
        save_plugin_settings('weather', settings)
        flash('Weather settings updated.', 'success')
        return redirect(url_for('weather.settings'))

    # Render the settings form
    return render_template('settings.html', settings=settings)

@weather_bp.route('/weather')
def display_weather():
    # Load settings and fetch weather data
    settings = load_plugin_settings('weather')
    params = {
        'lat': settings.get('latitude'),
        'lon': settings.get('longitude'),
        'units': settings.get('units', 'metric'),
        'appid': settings.get('api_key')
    }
    resp = requests.get('https://api.openweathermap.org/data/2.5/weather', params=params)
    api_data = resp.json()

    # Parse the API response into your internal structure
    weather_data = parse_api_response(api_data)

    # Override display name if user provided one
    manual = settings.get('manual_location_name', '')
    if manual:
        weather_data['location_name'] = manual
    else:
        default_name = api_data.get('name', '')
        country      = api_data.get('sys', {}).get('country', '')
        weather_data['location_name'] = f"{default_name}, {country}" if country else default_name

    # Render the e-ink display template
    return render_template('weather.html', weather=weather_data)
