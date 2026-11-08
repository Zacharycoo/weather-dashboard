import math
from datetime import datetime
from difflib import get_close_matches

import requests
from flask import Flask, jsonify, render_template, request, url_for

from weather import (
    GEOCODING_URL,
    get_city_coordinates,
    get_weather,
    get_weather_description,
    get_weather_icon
)

app = Flask(__name__)

US_STATES = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California",
    "Colorado", "Connecticut", "Delaware", "Florida", "Georgia",
    "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa",
    "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland",
    "Massachusetts", "Michigan", "Minnesota", "Mississippi",
    "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire",
    "New Jersey", "New Mexico", "New York", "North Carolina",
    "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania",
    "Rhode Island", "South Carolina", "South Dakota", "Tennessee",
    "Texas", "Utah", "Vermont", "Virginia", "Washington",
    "West Virginia", "Wisconsin", "Wyoming"
]

STATE_CITIES = {
    "Florida": [
        "Jacksonville", "Miami", "Tampa", "Orlando", "Tallahassee"
    ],
    "Texas": [
        "Houston", "San Antonio", "Dallas", "Austin", "Fort Worth"
    ],
    "Oklahoma": [
        "Oklahoma City", "Tulsa", "Norman", "Broken Arrow", "Edmond"
    ],
    "California": [
        "Los Angeles", "San Diego", "San Jose",
        "San Francisco", "Fresno"
    ],
    "New York": [
        "New York", "Buffalo", "Yonkers", "Rochester", "Syracuse"
    ]
}


def weather_theme(code):
    if code in (71, 73, 75, 77, 85, 86):
        return "snowy"

    if code in (
        51, 53, 55, 56, 57, 61, 63, 65, 66, 67,
        80, 81, 82, 95, 96, 99
    ):
        return "rainy"

    if code in (0, 1):
        return "sunny"

    return "cloudy"


def find_city_suggestion(city):
    """
    Find a close spelling match from the known city list.

    Suggestions are limited to known city names to avoid
    suggesting unrelated locations.
    """
    city_name = city.split(",")[0].strip()

    if not city_name:
        return None

    known_cities = {}

    for state, cities in STATE_CITIES.items():
        for name in cities:
            key = name.casefold()
            known_cities.setdefault(key, []).append((name, state))

    matches = get_close_matches(
        city_name.casefold(),
        list(known_cities.keys()),
        n=1,
        cutoff=0.78
    )

    if not matches:
        return None

    possible_locations = known_cities[matches[0]]

    # If the user included a state, prefer that state.
    parts = [part.strip() for part in city.split(",")]
    requested_state = parts[1] if len(parts) > 1 else ""

    if requested_state:
        for name, state in possible_locations:
            if state.casefold() == requested_state.casefold():
                return {
                    "name": name,
                    "state": state,
                    "url": url_for("home", city=f"{name}, {state}")
                }

        # Do not suggest a city in the wrong state.
        return None

    # Avoid ambiguous suggestions for duplicate city names.
    if len(possible_locations) != 1:
        return None

    name, state = possible_locations[0]

    return {
        "name": name,
        "state": state,
        "url": url_for("home", city=f"{name}, {state}")
    }


def show_error(title, message, city="", status=404,
               allow_suggestion=False):
    suggestion = None

    if allow_suggestion:
        suggestion = find_city_suggestion(city)

    return render_template(
        "error.html",
        title=title,
        message=message,
        city=city,
        suggestion=suggestion,
        theme="cloudy"
    ), status


@app.route("/")
def home():
    city = request.args.get("city", "Tulsa").strip()
    latitude_text = request.args.get("latitude")
    longitude_text = request.args.get("longitude")
    selected_state = request.args.get("state", "").strip()

    if not city:
        return show_error(
            title="City Not Found",
            message="Please enter a city name.",
            status=400
        )

    if latitude_text is not None or longitude_text is not None:
        try:
            if latitude_text is None or longitude_text is None:
                raise ValueError("Missing coordinate")

            latitude = float(latitude_text)
            longitude = float(longitude_text)

            if (
                not math.isfinite(latitude)
                or not math.isfinite(longitude)
                or not -90 <= latitude <= 90
                or not -180 <= longitude <= 180
            ):
                raise ValueError("Invalid coordinates")

        except (ValueError, TypeError):
            return show_error(
                title="Invalid Location",
                message="The selected city coordinates are invalid. Please search again.",
                city=city,
                status=400
            )

        location = {
            "name": city.split(",")[0].strip(),
            "state": selected_state,
            "latitude": latitude,
            "longitude": longitude
        }

    else:
        try:
            location = get_city_coordinates(city)

        except (requests.RequestException, ValueError, KeyError, TypeError):
            return show_error(
                title="Weather Service Unavailable",
                message="We couldn't search for your city right now. Please try again shortly.",
                city=city,
                status=503
            )

        if location is None:
            return show_error(
                title="City Not Found",
                message=f'We couldn\'t find a city named "{city}".',
                city=city,
                status=404,
                allow_suggestion=True
            )

    try:
        weather_data = get_weather(
            location["latitude"],
            location["longitude"]
        )

        weather = weather_data["current"]
        forecast = weather_data["daily"]

        if not weather or not forecast:
            raise ValueError("Missing weather data")

        forecast["days"] = [
            datetime.strptime(date, "%Y-%m-%d").strftime("%A")
            for date in forecast["time"]
        ]

        forecast["descriptions"] = [
            get_weather_description(code)
            for code in forecast["weather_code"]
        ]

        forecast["icons"] = [
            get_weather_icon(code)
            for code in forecast["weather_code"]
        ]

        # Ensure there is enough data for five forecast cards.
        if not all(
            len(forecast[key]) >= 5
            for key in (
                "days",
                "descriptions",
                "icons",
                "temperature_2m_max",
                "temperature_2m_min"
            )
        ):
            raise ValueError("Incomplete forecast")

        description = get_weather_description(
            weather["weather_code"]
        )

        current_icon = get_weather_icon(
            weather["weather_code"]
        )

        theme = weather_theme(weather["weather_code"])

    except (
        requests.RequestException,
        ValueError,
        KeyError,
        TypeError,
        IndexError,
        AttributeError
    ):
        return show_error(
            title="Weather Unavailable",
            message="We couldn't load the weather for this location. Please try again shortly.",
            city=city,
            status=503
        )

    display_city = ", ".join(
        part for part in (
            location["name"],
            location.get("state", "")
        )
        if part
    )

    return render_template(
        "index.html",
        weather=weather,
        description=description,
        city=display_city,
        forecast=forecast,
        current_icon=current_icon,
        theme=theme
    )


@app.route("/state-cities")
def state_cities():
    state = request.args.get("state", "").strip()
    return jsonify(STATE_CITIES.get(state, []))


@app.route("/autocomplete")
def autocomplete():
    query = request.args.get("q", "").strip()
    state_filter = request.args.get("state", "").strip()

    if len(query) < 2:
        return jsonify([])

    suggestions = []

    if not state_filter:
        suggestions = [
            {
                "name": state,
                "state": "",
                "country": "United States",
                "type": "state"
            }
            for state in US_STATES
            if state.lower().startswith(query.lower())
        ]

    try:
        response = requests.get(
            GEOCODING_URL,
            params={
                "name": query,
                "count": 100 if state_filter else 20,
                "language": "en",
                "format": "json"
            },
            timeout=8
        )

        response.raise_for_status()
        data = response.json()

    except (requests.RequestException, ValueError):
        data = {}

    for location in data.get("results", []):
        location_state = location.get("admin1", "")
        location_country = location.get("country", "")

        if state_filter and (
            location_state.casefold() != state_filter.casefold()
            or location_country != "United States"
        ):
            continue

        suggestions.append({
            "name": location["name"],
            "state": location_state,
            "country": location_country,
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "type": "city"
        })

    return jsonify(suggestions)


if __name__ == "__main__":
    app.run(debug=True)
