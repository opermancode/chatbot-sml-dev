import re
import requests
from datetime import datetime, timedelta, timezone
from models import db, User, ChatLog
from services.weather_service import (
    get_weather, get_hourly_forecast,
    format_current_weather, format_hourly_forecast,
)

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

user_state = {}


def welcome_msg(user):
    lines = [f"👋 *Hello {user.name}!*"]
    if user.site:
        lines.append(f"📍 Site: {user.site}")
    if user.city:
        lines.append(f"🏙 City: {user.city}")
    lines.append("")
    lines.append("🌤 *Sangreen Renewables Weather Bot*")
    lines.append("")
    lines.append("Choose an option:")
    lines.append("1️⃣ *Current Weather*")
    lines.append("2️⃣ *Forecast for a Date*")
    lines.append("")
    lines.append("Reply with 1 or 2")
    return "\n".join(lines)


CURRENT_WEATHER_MENU = """📍 *Get Current Weather*

How would you like to share your location?

1️⃣ *Share Live Location* (recommended)
2️⃣ *Enter City Name*

Reply with 1 or 2"""

LOCATION_PROMPT = """📍 *Share Your Live Location*

Tap the 📎 button → *Location* → *Share Live Location*.

Once received, I'll fetch the weather!"""

CITY_PROMPT = "🏙 Type your city name (e.g. Mumbai, Pune, Delhi):"

DATE_PROMPT = """📅 *Forecast for a Date*

Enter a date within the next 16 days in *DD-MM-YYYY* format.

Example: 05-07-2026"""

FORECAST_LOC_MENU = """📍 *Location for Forecast*

How would you like to choose the location?

1️⃣ *Share Live Location*
2️⃣ *Enter City Name*

Reply with 1 or 2"""

INVALID_DATE = """❌ Invalid date or out of range.

Enter a date within the next 16 days in *DD-MM-YYYY* format (e.g. 05-07-2026).

Reply *0* to go back to menu."""


def today():
    return datetime.now(timezone.utc).date()


def max_forecast_date():
    return today() + timedelta(days=16)


def parse_date(text):
    match = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{4})$", text.strip())
    if not match:
        return None
    day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
    try:
        return datetime(year, month, day).date()
    except ValueError:
        return None


def get_or_create_user(phone):
    return User.query.filter_by(phone=phone).first()


def log_chat(phone, message, response, direction,
             message_type="text", user_id=None):
    chat = ChatLog(
        user_id=user_id, phone=phone, message=message,
        response=response, direction=direction, message_type=message_type,
    )
    db.session.add(chat)
    db.session.commit()


def geocode_city(city_name):
    try:
        resp = requests.get(
            GEOCODING_URL,
            params={"name": city_name, "count": 1, "language": "en", "format": "json"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return None
        r = results[0]
        return {
            "lat": r["latitude"],
            "lon": r["longitude"],
            "name": r.get("name", city_name),
            "country": r.get("country", ""),
        }
    except Exception:
        return None


def weather_for_city(city_name):
    geo = geocode_city(city_name)
    if not geo:
        return f"Sorry, couldn't find a city named '{city_name}'."
    data = get_weather(geo["lat"], geo["lon"])
    weather = format_current_weather(data)
    return f"📍 *Weather for {geo['name']}, {geo['country']}*\n\n{weather}"


def weather_for_coords(lat, lon):
    data = get_weather(lat, lon)
    return format_current_weather(data)


def hourly_for_location(lat, lon, date_str, label=""):
    data = get_hourly_forecast(lat, lon, date_str)
    if "error" in data:
        return "Sorry, couldn't fetch forecast data."
    return format_hourly_forecast(data, label, date_str)


def hourly_for_city_name(city_name, date_str):
    geo = geocode_city(city_name)
    if not geo:
        return None, f"Sorry, couldn't find a city named '{city_name}'."
    forecast = hourly_for_location(geo["lat"], geo["lon"], date_str, geo["name"])
    return geo, forecast


def handle_incoming(phone, message):
    user = get_or_create_user(phone)
    user_id = user.id if user else None

    if not user:
        return None

    msg = message.strip().lower()
    state = user_state.get(phone, "menu")

    # Back to main menu
    if msg in ("0", "menu", "main menu"):
        user_state[phone] = "menu"
        resp = welcome_msg(user)
        log_chat(phone, message, resp, "outgoing", user_id=user_id)
        return resp

    # Hi / start
    if msg in ("hi", "hello", "hey", "start"):
        user_state[phone] = "menu"
        resp = welcome_msg(user)
        log_chat(phone, message, resp, "outgoing", user_id=user_id)
        return resp

    # ─── Awaiting city name for current weather ────────────────────────
    if state == "awaiting_city":
        user_state[phone] = "menu"
        resp = weather_for_city(message.strip())
        log_chat(phone, message, resp, "outgoing",
                 message_type="city_weather", user_id=user_id)
        return resp + "\n\nReply *0* for main menu."

    # ─── Awaiting date for forecast ────────────────────────────────────
    if state == "awaiting_forecast_date":
        date = parse_date(message)
        if date is None:
            log_chat(phone, message, INVALID_DATE, "outgoing", user_id=user_id)
            return INVALID_DATE

        if date < today() or date > max_forecast_date():
            log_chat(phone, message, INVALID_DATE, "outgoing", user_id=user_id)
            return INVALID_DATE

        # Store date and ask for location
        user_state[phone] = "awaiting_forecast_loc"
        user_state[phone + "_fdate"] = date.strftime("%Y-%m-%d")
        resp = FORECAST_LOC_MENU
        log_chat(phone, message, resp, "outgoing", user_id=user_id)
        return resp

    # ─── Awaiting location choice for forecast ─────────────────────────
    if state == "awaiting_forecast_loc":
        if msg == "1":
            user_state[phone] = "awaiting_forecast_coords"
            resp = LOCATION_PROMPT
            log_chat(phone, message, resp, "outgoing",
                     message_type="location_prompt", user_id=user_id)
            return resp
        if msg == "2":
            user_state[phone] = "awaiting_forecast_city"
            resp = CITY_PROMPT
            log_chat(phone, message, resp, "outgoing", user_id=user_id)
            return resp
        resp = "Please reply with:\n1️⃣ Share Live Location\n2️⃣ Enter City Name"
        log_chat(phone, message, resp, "outgoing", user_id=user_id)
        return resp

    # ─── Awaiting city name for forecast ───────────────────────────────
    if state == "awaiting_forecast_city":
        date_str = user_state.get(phone + "_fdate")
        if not date_str:
            user_state[phone] = "menu"
            resp = "Something went wrong. Please start again."
            log_chat(phone, message, resp, "outgoing", user_id=user_id)
            return resp

        city = message.strip()
        geo, forecast = hourly_for_city_name(city, date_str)
        if not geo:
            resp = forecast  # error message
            log_chat(phone, message, resp, "outgoing", user_id=user_id)
            return resp

        user_state[phone] = "menu"
        log_chat(phone, message, forecast, "outgoing",
                 message_type="forecast_city", user_id=user_id)
        return forecast + "\n\nReply *0* for main menu."

    # ─── Weather sub-menu ──────────────────────────────────────────────
    if state == "weather_menu":
        if msg == "1":
            resp = LOCATION_PROMPT
            log_chat(phone, message, resp, "outgoing",
                     message_type="location_prompt", user_id=user_id)
            return resp
        if msg == "2":
            user_state[phone] = "awaiting_city"
            resp = CITY_PROMPT
            log_chat(phone, message, resp, "outgoing", user_id=user_id)
            return resp
        resp = "Please reply with:\n1️⃣ Share Live Location\n2️⃣ Enter City Name"
        log_chat(phone, message, resp, "outgoing", user_id=user_id)
        return resp

    # ─── Main menu ─────────────────────────────────────────────────────
    if msg == "1":
        user_state[phone] = "weather_menu"
        resp = CURRENT_WEATHER_MENU
        log_chat(phone, message, resp, "outgoing", user_id=user_id)
        return resp

    if msg == "2":
        user_state[phone] = "awaiting_forecast_date"
        resp = DATE_PROMPT
        log_chat(phone, message, resp, "outgoing", user_id=user_id)
        return resp

    # ─── Fallback ──────────────────────────────────────────────────────
    resp = (
        "I didn't understand that. Reply with:\n"
        "1️⃣ Current Weather\n"
        "2️⃣ Forecast for a Date\n"
        "0️⃣ Main Menu"
    )
    log_chat(phone, message, resp, "outgoing", user_id=user_id)
    return resp


def handle_location(phone, lat, lon):
    user = get_or_create_user(phone)
    user_id = user.id if user else None

    state = user_state.get(phone, "menu")

    # If waiting for forecast coordinates
    if state == "awaiting_forecast_coords":
        date_str = user_state.get(phone + "_fdate")
        if date_str:
            forecast = hourly_for_location(lat, lon, date_str, "Your Location")
            user_state[phone] = "menu"
            log_chat(phone, f"Location shared: {lat},{lon}", forecast,
                     "outgoing", message_type="forecast_location", user_id=user_id)
            return forecast + "\n\nReply *0* for main menu."

    # Default: current weather
    weather = weather_for_coords(lat, lon)
    log_chat(phone, f"Location shared: {lat},{lon}", weather,
             "outgoing", message_type="location", user_id=user_id)
    return weather + "\n\nReply *0* for main menu."
