import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def get_city_coordinates(city):
    response = requests.get(
        GEOCODING_URL,
        params={
            "name": city,
            "count": 10,
            "language": "en",
            "format": "json"
        },
        timeout=10
    )
    response.raise_for_status()

    results = response.json().get("results", [])
    if not results:
        return None

    location = results[0]
    return {
        "name": location["name"],
        "state": location.get("admin1", ""),
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "country": location.get("country", "")
    }


def get_weather(latitude, longitude):
    response = requests.get(
        FORECAST_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": (
                "temperature_2m,relative_humidity_2m,"
                "wind_speed_10m,weather_code"
            ),
            "daily": (
                "weather_code,temperature_2m_max,"
                "temperature_2m_min"
            ),
            "forecast_days": 5,
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "timezone": "auto"
        },
        timeout=10
    )
    response.raise_for_status()
    return response.json()


DESCRIPTIONS = {
    0: "Clear Sky",
    1: "Mainly Clear",
    2: "Partly Cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Freezing Fog",
    51: "Light Drizzle",
    53: "Moderate Drizzle",
    55: "Heavy Drizzle",
    56: "Light Freezing Drizzle",
    57: "Heavy Freezing Drizzle",
    61: "Light Rain",
    63: "Moderate Rain",
    65: "Heavy Rain",
    66: "Light Freezing Rain",
    67: "Heavy Freezing Rain",
    71: "Light Snow",
    73: "Moderate Snow",
    75: "Heavy Snow",
    77: "Snow Grains",
    80: "Light Rain Showers",
    81: "Moderate Rain Showers",
    82: "Heavy Rain Showers",
    85: "Light Snow Showers",
    86: "Heavy Snow Showers",
    95: "Thunderstorm",
    96: "Thunderstorm with Hail",
    99: "Severe Thunderstorm with Hail"
}


def get_weather_description(code):
    return DESCRIPTIONS.get(code, "Unknown Weather")


def get_weather_icon(code):
    """Return the SVG symbol name for the weather code."""
    if code == 0:
        return "sun"
    if code in (1, 2):
        return "partly-cloudy"
    if code in (3, 45, 48):
        return "cloud"
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67,
                80, 81, 82):
        return "rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (95, 96, 99):
        return "storm"
    return "cloud"
