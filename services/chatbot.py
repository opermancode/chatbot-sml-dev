import re
import requests
from datetime import datetime, timedelta, timezone
from models import db, User, ChatLog, Setting
from services.localization import (
    LANGUAGE_BY_NUMBER,
    LANGUAGE_NAMES,
    language_menu,
    t,
)
from services.weather_service import (
    get_weather, get_hourly_forecast,
    format_current_with_hourly,
    format_hourly_forecast,
)

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

user_state = {}

WIND_HEIGHT_BY_NUMBER = {
    "1": "10m",
    "2": "80m",
    "3": "120m",
    "4": "180m",
}


def get_setting(key, default=""):
    setting = Setting.query.filter_by(key=key).first()
    return setting.value if setting else default


def set_setting(key, value):
    setting = Setting.query.filter_by(key=key).first()
    if setting:
        setting.value = value
    else:
        db.session.add(Setting(key=key, value=value))
    db.session.commit()


def language_key(phone):
    return f"user_language:{phone}"


def get_user_language(phone):
    return get_setting(language_key(phone), "en")


def save_user_language(phone, lang):
    set_setting(language_key(phone), lang)


def has_user_language(phone):
    return bool(get_setting(language_key(phone), ""))


def wind_height_menu(lang, invalid=False):
    title = t(lang, "height_invalid") if invalid else t(lang, "height_question")
    lines = [f"🌬 *{title}*", ""]
    lines.append("1️⃣ 10m")
    lines.append("2️⃣ 80m")
    lines.append("3️⃣ 120m")
    lines.append("4️⃣ 180m")
    lines.append("")
    lines.append(t(lang, "height_hint"))
    return "\n".join(lines)


def welcome_msg(user, lang="en"):
    lines = [f"👋 *{t(lang, 'hello')} {user.name}!*"]
    if user.site:
        lines.append(f"📍 {t(lang, 'site')}: {user.site}")
    if user.city:
        lines.append(f"🏙 {t(lang, 'city')}: {user.city}")
    lines.append("")
    lines.append(f"🌤 *{t(lang, 'weather_bot')}*")
    lines.append("")
    lines.append(t(lang, "choose_option"))
    lines.append(f"1️⃣ *{t(lang, 'current_weather')}*")
    lines.append(f"2️⃣ *{t(lang, 'forecast_date')}*")
    lines.append("")
    lines.append(t(lang, "reply_1_2"))
    return "\n".join(lines)


def current_weather_menu(lang):
    return "\n".join([
        f"📍 *{t(lang, 'get_current')}*",
        "",
        t(lang, "share_how"),
        "",
        f"1️⃣ *{t(lang, 'share_live_rec')}*",
        f"2️⃣ *{t(lang, 'enter_city')}*",
        "",
        t(lang, "reply_1_2"),
    ])


def location_prompt(lang):
    return f"📍 *{t(lang, 'location_prompt_title')}*\n\n{t(lang, 'location_prompt_body')}"


def city_prompt(lang):
    return f"🏙 {t(lang, 'city_prompt')}"


def date_prompt(lang):
    return "\n".join([
        f"📅 *{t(lang, 'forecast_title')}*",
        "",
        t(lang, "forecast_body"),
        "",
        f"{t(lang, 'example')}: {today().strftime('%d-%m-%Y')}",
    ])


def forecast_loc_menu(lang):
    return "\n".join([
        f"📍 *{t(lang, 'forecast_location')}*",
        "",
        t(lang, "share_how"),
        "",
        f"1️⃣ *{t(lang, 'share_live')}*",
        f"2️⃣ *{t(lang, 'enter_city')}*",
        "",
        t(lang, "reply_1_2"),
    ])


def invalid_date_msg(lang):
    return f"❌ {t(lang, 'invalid_date')}\n\n{t(lang, 'back_menu')}"


def option_1_2_msg(lang):
    return (
        f"{t(lang, 'please_reply')}\n"
        f"1️⃣ {t(lang, 'share_live')}\n"
        f"2️⃣ {t(lang, 'enter_city')}"
    )


def fallback_msg(lang):
    return (
        f"{t(lang, 'unknown')}\n"
        f"1️⃣ {t(lang, 'current_weather')}\n"
        f"2️⃣ {t(lang, 'forecast_date')}\n"
        f"0️⃣ {t(lang, 'main_menu')}"
    )


def today():
    return datetime.now(timezone.utc).date()


def today_ist_str():
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist).date().strftime("%Y-%m-%d")


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


def weather_for_city(city_name, lang="en", wind_height="10m"):
    geo = geocode_city(city_name)
    if not geo:
        return f"{t(lang, 'not_found_city')} '{city_name}'."
    data = get_weather(geo["lat"], geo["lon"])
    hourly = get_hourly_forecast(geo["lat"], geo["lon"], today_ist_str())
    weather = format_current_with_hourly(
        data,
        hourly,
        city_name=geo["name"],
        date=today_ist_str(),
        lang=lang,
        wind_height=wind_height,
    )
    return f"📍 *{t(lang, 'weather_for')} {geo['name']}, {geo['country']}*\n\n{weather}"


def weather_for_coords(lat, lon, lang="en", wind_height="10m"):
    data = get_weather(lat, lon)
    date_str = today_ist_str()
    hourly = get_hourly_forecast(lat, lon, date_str)
    return format_current_with_hourly(
        data,
        hourly,
        city_name="Your Location",
        date=date_str,
        lang=lang,
        wind_height=wind_height,
    )


def hourly_for_location(lat, lon, date_str, label="", lang="en"):
    data = get_hourly_forecast(lat, lon, date_str)
    if "error" in data:
        return t(lang, "fetch_forecast_error")
    return format_hourly_forecast(data, label, date_str, lang=lang)


def hourly_for_city_name(city_name, date_str, lang="en"):
    geo = geocode_city(city_name)
    if not geo:
        return None, f"{t(lang, 'not_found_city')} '{city_name}'."
    forecast = hourly_for_location(geo["lat"], geo["lon"], date_str, geo["name"], lang=lang)
    return geo, forecast


def handle_incoming(phone, message):
    user = get_or_create_user(phone)
    user_id = user.id if user else None

    if not user:
        return None

    msg = message.strip().lower()
    state = user_state.get(phone, "menu")
    lang = get_user_language(phone)

    if msg in ("language", "lang", "change language", "भाषा"):
        user_state[phone] = "awaiting_language"
        resp = language_menu()
        log_chat(phone, message, resp, "outgoing", message_type="language", user_id=user_id)
        return resp

    if state == "awaiting_language":
        selected = LANGUAGE_BY_NUMBER.get(msg)
        if not selected:
            resp = language_menu()
            log_chat(phone, message, resp, "outgoing", message_type="language", user_id=user_id)
            return resp
        save_user_language(phone, selected)
        lang = get_user_language(phone)
        user_state[phone] = "menu"
        resp = (
            f"✅ *{t(lang, 'language_saved')}:* {LANGUAGE_NAMES.get(selected, selected)}\n\n"
            f"{welcome_msg(user, lang)}"
        )
        log_chat(phone, message, resp, "outgoing", message_type="language", user_id=user_id)
        return resp

    # Back to main menu
    if msg in ("0", "menu", "main menu"):
        user_state[phone] = "menu"
        resp = welcome_msg(user, lang)
        log_chat(phone, message, resp, "outgoing", user_id=user_id)
        return resp

    # Hi / start
    if msg in ("hi", "hello", "hey", "start"):
        if not has_user_language(phone):
            user_state[phone] = "awaiting_language"
            resp = language_menu()
            log_chat(phone, message, resp, "outgoing", message_type="language", user_id=user_id)
            return resp
        user_state[phone] = "menu"
        resp = welcome_msg(user, lang)
        log_chat(phone, message, resp, "outgoing", user_id=user_id)
        return resp

    if not has_user_language(phone):
        user_state[phone] = "awaiting_language"
        resp = language_menu()
        log_chat(phone, message, resp, "outgoing", message_type="language", user_id=user_id)
        return resp

    if state == "awaiting_current_wind_height":
        wind_height = WIND_HEIGHT_BY_NUMBER.get(msg)
        if not wind_height:
            resp = wind_height_menu(lang, invalid=True)
            log_chat(phone, message, resp, "outgoing", message_type="wind_height", user_id=user_id)
            return resp

        lat = user_state.get(phone + "_lat")
        lon = user_state.get(phone + "_lon")
        if lat is None or lon is None:
            user_state[phone] = "menu"
            resp = t(lang, "something_wrong")
            log_chat(phone, message, resp, "outgoing", user_id=user_id)
            return resp

        user_state[phone] = "menu"
        weather = weather_for_coords(lat, lon, lang=lang, wind_height=wind_height)
        resp = weather + "\n\n" + t(lang, "reply_main")
        log_chat(phone, message, resp, "outgoing",
                 message_type="location_weather", user_id=user_id)
        return resp

    # ─── Awaiting city name for current weather ────────────────────────
    if state == "awaiting_city":
        user_state[phone] = "menu"
        resp = weather_for_city(message.strip(), lang=lang)
        log_chat(phone, message, resp, "outgoing",
                 message_type="city_weather", user_id=user_id)
        return resp + "\n\n" + t(lang, "reply_main")

    # ─── Awaiting date for forecast ────────────────────────────────────
    if state == "awaiting_forecast_date":
        date = parse_date(message)
        if date is None:
            resp = invalid_date_msg(lang)
            log_chat(phone, message, resp, "outgoing", user_id=user_id)
            return resp

        if date < today() or date > max_forecast_date():
            resp = invalid_date_msg(lang)
            log_chat(phone, message, resp, "outgoing", user_id=user_id)
            return resp

        # Store date and ask for location
        user_state[phone] = "awaiting_forecast_loc"
        user_state[phone + "_fdate"] = date.strftime("%Y-%m-%d")
        resp = forecast_loc_menu(lang)
        log_chat(phone, message, resp, "outgoing", user_id=user_id)
        return resp

    # ─── Awaiting location choice for forecast ─────────────────────────
    if state == "awaiting_forecast_loc":
        if msg == "1":
            user_state[phone] = "awaiting_forecast_coords"
            resp = location_prompt(lang)
            log_chat(phone, message, resp, "outgoing",
                     message_type="location_prompt", user_id=user_id)
            return resp
        if msg == "2":
            user_state[phone] = "awaiting_forecast_city"
            resp = city_prompt(lang)
            log_chat(phone, message, resp, "outgoing", user_id=user_id)
            return resp
        resp = option_1_2_msg(lang)
        log_chat(phone, message, resp, "outgoing", user_id=user_id)
        return resp

    # ─── Awaiting city name for forecast ───────────────────────────────
    if state == "awaiting_forecast_city":
        date_str = user_state.get(phone + "_fdate")
        if not date_str:
            user_state[phone] = "menu"
            resp = t(lang, "something_wrong")
            log_chat(phone, message, resp, "outgoing", user_id=user_id)
            return resp

        city = message.strip()
        geo, forecast = hourly_for_city_name(city, date_str, lang=lang)
        if not geo:
            resp = forecast  # error message
            log_chat(phone, message, resp, "outgoing", user_id=user_id)
            return resp

        user_state[phone] = "menu"
        log_chat(phone, message, forecast, "outgoing",
                 message_type="forecast_city", user_id=user_id)
        return forecast + "\n\n" + t(lang, "reply_main")

    # ─── Weather sub-menu ──────────────────────────────────────────────
    if state == "weather_menu":
        if msg == "1":
            resp = location_prompt(lang)
            log_chat(phone, message, resp, "outgoing",
                     message_type="location_prompt", user_id=user_id)
            return resp
        if msg == "2":
            user_state[phone] = "awaiting_city"
            resp = city_prompt(lang)
            log_chat(phone, message, resp, "outgoing", user_id=user_id)
            return resp
        resp = option_1_2_msg(lang)
        log_chat(phone, message, resp, "outgoing", user_id=user_id)
        return resp

    # ─── Main menu ─────────────────────────────────────────────────────
    if msg == "1":
        user_state[phone] = "weather_menu"
        resp = current_weather_menu(lang)
        log_chat(phone, message, resp, "outgoing", user_id=user_id)
        return resp

    if msg == "2":
        user_state[phone] = "awaiting_forecast_date"
        resp = date_prompt(lang)
        log_chat(phone, message, resp, "outgoing", user_id=user_id)
        return resp

    # ─── Fallback ──────────────────────────────────────────────────────
    resp = fallback_msg(lang)
    log_chat(phone, message, resp, "outgoing", user_id=user_id)
    return resp


def handle_location(phone, lat, lon):
    user = get_or_create_user(phone)
    user_id = user.id if user else None
    lang = get_user_language(phone)

    state = user_state.get(phone, "menu")

    # If waiting for forecast coordinates
    if state == "awaiting_forecast_coords":
        date_str = user_state.get(phone + "_fdate")
        if date_str:
            forecast = hourly_for_location(lat, lon, date_str, "Your Location", lang=lang)
            user_state[phone] = "menu"
            log_chat(phone, f"Location shared: {lat},{lon}", forecast,
                     "outgoing", message_type="forecast_location", user_id=user_id)
            return forecast + "\n\n" + t(lang, "reply_main")

    # Default: ask for wind height before current weather.
    user_state[phone] = "awaiting_current_wind_height"
    user_state[phone + "_lat"] = lat
    user_state[phone + "_lon"] = lon
    resp = wind_height_menu(lang)
    log_chat(phone, f"Location shared: {lat},{lon}", resp,
             "outgoing", message_type="wind_height_prompt", user_id=user_id)
    return resp
