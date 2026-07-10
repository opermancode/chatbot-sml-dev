import re
import requests
from datetime import datetime
from services.localization import t

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def get_weather(lat: float, lon: float):
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "weather_code",
            "wind_speed_10m_max",
        ],
        "current": [
            "temperature_2m", "relative_humidity_2m",
            "apparent_temperature", "precipitation",
            "precipitation_probability", "cloud_cover",
            "pressure_msl",
            "weather_code", "wind_speed_10m",
            "wind_gusts_10m", "wind_direction_10m",
            "wind_speed_80m", "wind_speed_120m", "wind_speed_180m",
        ],
        "timezone": "Asia/Kolkata",
        "forecast_days": 16,
    }
    try:
        resp = requests.get(OPEN_METEO_URL, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


WEATHER_CODES = {
    0: "Clear sky ☀️",
    1: "Mainly clear 🌤",
    2: "Partly cloudy ⛅",
    3: "Overcast ☁️",
    45: "Foggy 🌫",
    48: "Depositing rime fog 🌫",
    51: "Light drizzle 🌦",
    53: "Moderate drizzle 🌦",
    55: "Dense drizzle 🌦",
    61: "Slight rain 🌧",
    63: "Moderate rain 🌧",
    65: "Heavy rain 🌧",
    71: "Slight snow 🌨",
    73: "Moderate snow 🌨",
    75: "Heavy snow 🌨",
    80: "Slight rain showers 🌦",
    81: "Moderate rain showers 🌦",
    82: "Violent rain showers 🌦",
    95: "Thunderstorm ⛈",
    96: "Thunderstorm with slight hail ⛈",
    99: "Thunderstorm with heavy hail ⛈",
}


def weather_code_desc(code: int):
    return WEATHER_CODES.get(code, f"Unknown ({code})")


WIND_DIRECTIONS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]


def wind_dir_label(degrees):
    if degrees is None:
        return ""
    idx = round(degrees / 22.5) % 16
    return WIND_DIRECTIONS[idx]


def wind_label(speed):
    if speed is None:
        return ""
    if speed < 5:
        return "Calm"
    if speed < 20:
        return "Light"
    if speed < 30:
        return "Moderate"
    if speed < 40:
        return "Strong"
    if speed < 55:
        return "Very Strong"
    return "Gale ⚠️"


WIND_HEIGHT_FIELDS = {
    "10m": "wind_speed_10m",
    "80m": "wind_speed_80m",
    "120m": "wind_speed_120m",
    "180m": "wind_speed_180m",
}


def fmt_num(value, suffix=""):
    if value is None:
        return "-"
    if isinstance(value, float):
        value = round(value, 1)
        if value == int(value):
            value = int(value)
    return f"{value}{suffix}"


def format_current_weather(data: dict, lang="en", wind_height="10m") -> str:
    if "error" in data:
        return t(lang, "fetch_weather_error")

    current = data.get("current", {})
    if not current:
        return t(lang, "no_weather")

    wcode = current.get("weather_code", -1)
    desc = weather_code_desc(wcode)
    temp = current.get("temperature_2m", "N/A")
    feels = current.get("apparent_temperature")
    humidity = current.get("relative_humidity_2m", "N/A")
    cloud = current.get("cloud_cover", "N/A")
    rain_chance = current.get("precipitation_probability")
    rain_mm = current.get("precipitation", 0)
    pressure = current.get("pressure_msl")

    wind_10m = current.get("wind_speed_10m", 0)
    gust = current.get("wind_gusts_10m")
    wind_dir = current.get("wind_direction_10m")
    wind_dir_str = wind_dir_label(wind_dir)
    wind_80m = current.get("wind_speed_80m")
    wind_120m = current.get("wind_speed_120m")
    wind_180m = current.get("wind_speed_180m")
    wind_by_height = {
        "10m": wind_10m,
        "80m": wind_80m,
        "120m": wind_120m,
        "180m": wind_180m,
    }
    selected_wind = wind_by_height.get(wind_height, wind_10m)

    lines = [
        f"🌤 *{t(lang, 'live_weather')}*",
        "```",
        "Metric        Value",
        "----------------------",
        f"Condition     {desc}",
        f"Temp          {fmt_num(temp, '°C')}",
        f"Feels         {fmt_num(feels, '°C')}",
        f"Humidity      {fmt_num(humidity, '%')}",
        f"Cloud         {fmt_num(cloud, '%')}",
    ]
    if rain_chance is not None:
        lines.append(f"Rain chance   {fmt_num(rain_chance, '%')}")
    if rain_mm and rain_mm > 0:
        lines.append(f"Rain          {fmt_num(rain_mm, ' mm')}")
    if pressure:
        lines.append(f"Pressure      {fmt_num(pressure, ' hPa')}")
    lines.append("```")

    lines.append("")
    lines.append(f"🌬 *{t(lang, 'wind_report')}*")
    dir_info = f"({wind_dir_str})" if wind_dir_str else ""
    lines.append(f"*{t(lang, 'direction')}:* {wind_dir}° {dir_info}")
    lines.append(
        f"*{t(lang, 'selected_height')} ({wind_height}):* "
        f"{selected_wind if selected_wind is not None else 'N/A'} km/h"
    )
    lines.append(f"*{t(lang, 'ground')}:* {wind_10m} km/h - {wind_label(wind_10m)}")
    if gust is not None and gust > 0:
        lines.append(f"*{t(lang, 'gusts_ground')}:* {gust} km/h")

    lines.append("")
    return "\n".join(lines)


def get_hourly_forecast(lat: float, lon: float, date: str):
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": [
            "temperature_2m", "precipitation_probability",
            "precipitation", "weather_code",
            "wind_speed_10m", "wind_speed_80m",
            "wind_speed_120m", "wind_speed_180m",
            "wind_gusts_10m",
        ],
        "start_date": date,
        "end_date": date,
        "timezone": "Asia/Kolkata",
        "temporal_resolution": "minutely_30",
    }
    try:
        resp = requests.get(OPEN_METEO_URL, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def fmt(val, width):
    s = str(val) if val is not None else "—"
    return s.ljust(width)


def format_hourly_forecast(data: dict, city_name="", date="", lang="en", wind_height="10m") -> str:
    if "error" in data:
        return t(lang, "fetch_hourly_error")

    hourly = data.get("hourly", {})
    if not hourly or not hourly.get("time"):
        return t(lang, "no_hourly")

    times = hourly["time"]
    temps = hourly.get("temperature_2m", [])
    rain_chances = hourly.get("precipitation_probability", [])
    codes = hourly.get("weather_code", [])
    wind_field = WIND_HEIGHT_FIELDS.get(wind_height, "wind_speed_10m")
    winds = hourly.get(wind_field, [])

    # Format date for display
    date_display = date
    if date and len(date) == 10:
        try:
            d = datetime.strptime(date, "%Y-%m-%d")
            date_display = d.strftime("%d-%b-%Y")
        except ValueError:
            pass

    lines = [f"📅 *{t(lang, 'hourly_forecast')} - {city_name}*"]
    lines.append(f"📆 {date_display}")
    lines.append("")

    lines.append(f"Wind column: {wind_height}")
    lines.append("```")
    lines.append("Time  Rain  Wind  Temp  Condition")
    lines.append("-----------------------------------")

    for i in range(len(times)):
        time_str = times[i].split("T")[1][:5]
        temp = f"{temps[i]:.0f}°C" if i < len(temps) and temps[i] is not None else "-"
        rain = f"{rain_chances[i]:.0f}%" if i < len(rain_chances) and rain_chances[i] is not None else "-"
        wind = f"{winds[i]:.0f}" if i < len(winds) and winds[i] is not None else "-"
        wcode = codes[i] if i < len(codes) else -1
        cond = weather_code_desc(wcode)

        lines.append(
            f"{fmt(time_str, 5)} {fmt(rain, 5)} {fmt(wind, 5)} {fmt(temp, 6)} {cond}"
        )

    lines.append("```")
    lines.append("")
    lines.append(f"🛡 *Sangreen Renewables* - {t(lang, 'safe')}")
    return "\n".join(lines)


def format_current_with_hourly(data: dict, hourly_data: dict, city_name="Your Location",
                               date="", lang="en", wind_height="10m") -> str:
    current = format_current_weather(data, lang=lang, wind_height=wind_height)
    hourly = format_hourly_forecast(
        hourly_data,
        city_name=city_name,
        date=date,
        lang=lang,
        wind_height=wind_height,
    )
    return f"{current}\n{hourly}"


def format_weather_forecast(data: dict) -> str:
    if "error" in data:
        return "Sorry, couldn't fetch weather data right now. Try again later."

    current = data.get("current", {})
    daily = data.get("daily", {})

    if not current or not daily:
        return "Sorry, no weather data available."

    temp = current.get("temperature_2m", "N/A")
    humidity = current.get("relative_humidity_2m", "N/A")
    wind = current.get("wind_speed_10m", "N/A")
    wcode = current.get("weather_code", -1)
    desc = weather_code_desc(wcode)

    lines = [
        "🌤 *Current Weather*",
        f"Condition: {desc}",
        f"Temperature: {temp}°C",
        f"Humidity: {humidity}%",
        f"Wind Speed: {wind} km/h",
        "",
        "📅 *16-Day Forecast*",
    ]

    dates = daily.get("time", [])
    max_temps = daily.get("temperature_2m_max", [])
    min_temps = daily.get("temperature_2m_min", [])
    precip = daily.get("precipitation_sum", [])
    codes = daily.get("weather_code", [])

    for i in range(len(dates)):
        day_desc = weather_code_desc(codes[i]) if i < len(codes) else ""
        min_t = min_temps[i] if i < len(min_temps) else "?"
        max_t = max_temps[i] if i < len(max_temps) else "?"
        p = precip[i] if i < len(precip) else "?"
        lines.append(
            f"  {dates[i]}: {min_t}-{max_t}°C, "
            f"{p}mm rain, {day_desc}"
        )

    lines.append("")
    lines.append("⚠️ *Sangreen Renewables* — Stay safe!")
    return "\n".join(lines)
