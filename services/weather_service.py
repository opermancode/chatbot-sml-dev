import re
import requests
from datetime import datetime

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def get_weather(lat: float, lon: float):
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "weathercode",
            "wind_speed_10m_max",
        ],
        "current": [
            "temperature_2m", "relative_humidity_2m",
            "apparent_temperature", "precipitation",
            "precipitation_probability", "cloud_cover",
            "pressure_msl",
            "weathercode", "wind_speed_10m",
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


def format_current_weather(data: dict) -> str:
    if "error" in data:
        return "Sorry, couldn't fetch weather data right now. Try again later."

    current = data.get("current", {})
    if not current:
        return "Sorry, no weather data available."

    wcode = current.get("weathercode", -1)
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

    lines = [
        "🌤 *Live Weather at Your Site*",
        "",
        f"☁️  {desc}",
        f"🌡  {temp}°C" + (f"  (feels {feels}°C)" if feels is not None else ""),
        f"💧  Humidity: {humidity}%",
        f"☁️  Cloud Cover: {cloud}%",
    ]
    if rain_chance is not None:
        icon = "⛈" if rain_chance > 60 else "🌦" if rain_chance > 30 else "🌤"
        lines.append(f"{icon}  Rain Chance: {rain_chance}%")
    if rain_mm and rain_mm > 0:
        lines.append(f"🌧  Rain: {rain_mm} mm")
    if pressure:
        lines.append(f"🔽  Pressure: {pressure} hPa")

    lines.append("")
    lines.append("🌬 *Wind Report*")
    dir_info = f"({wind_dir_str})" if wind_dir_str else ""
    lines.append(f"Direction: {wind_dir}° {dir_info}")
    lines.append(f"Ground: {wind_10m} km/h — {wind_label(wind_10m)}")
    if gust is not None and gust > 0:
        lines.append(f"Gusts: {gust} km/h")
    if wind_80m is not None:
        lines.append(f"At 80m: {wind_80m} km/h")
    if wind_120m is not None:
        lines.append(f"At 120m: {wind_120m} km/h")
    if wind_180m is not None:
        lines.append(f"At 180m: {wind_180m} km/h")

    lines.append("")
    lines.append("🛡 *Sangreen Renewables* — Stay safe on site!")
    return "\n".join(lines)


def get_hourly_forecast(lat: float, lon: float, date: str):
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": [
            "temperature_2m", "precipitation_probability",
            "precipitation", "weathercode",
            "wind_speed_10m", "wind_gusts_10m",
        ],
        "start_date": date,
        "end_date": date,
        "timezone": "Asia/Kolkata",
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


def format_hourly_forecast(data: dict, city_name="", date="") -> str:
    if "error" in data:
        return "Sorry, couldn't fetch hourly weather data. Try again later."

    hourly = data.get("hourly", {})
    if not hourly or not hourly.get("time"):
        return "No hourly data available for that date."

    times = hourly["time"]
    temps = hourly.get("temperature_2m", [])
    rain_chances = hourly.get("precipitation_probability", [])
    codes = hourly.get("weathercode", [])
    winds = hourly.get("wind_speed_10m", [])

    # Format date for display
    date_display = date
    if date and len(date) == 10:
        try:
            d = datetime.strptime(date, "%Y-%m-%d")
            date_display = d.strftime("%d-%b-%Y")
        except ValueError:
            pass

    lines = [f"📅 *Hourly Forecast — {city_name}*"]
    lines.append(f"📆 {date_display}")
    lines.append("")

    # Table header
    lines.append("  Time    Temp   Rain   Wind   Condition")
    lines.append("  " + "─" * 38)

    for i in range(len(times)):
        time_str = times[i].split("T")[1][:5]
        temp = f"{temps[i]:.0f}°C" if i < len(temps) else "—"
        rain = f"{rain_chances[i]}%" if i < len(rain_chances) and rain_chances[i] > 0 else "—"
        wind = f"{winds[i]:.0f}" if i < len(winds) and winds[i] > 0 else "—"
        wcode = codes[i] if i < len(codes) else -1
        cond = weather_code_desc(wcode).split(" ")[0] if wcode not in (0, 1, 2, 3) else ""

        lines.append(
            f"  {fmt(time_str, 6)} {fmt(temp, 5)} {fmt(rain, 5)} {fmt(wind, 5)} {cond}"
        )

    lines.append("")
    lines.append("🛡 *Sangreen Renewables* — Stay safe on site!")
    return "\n".join(lines)


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
    wcode = current.get("weathercode", -1)
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
    codes = daily.get("weathercode", [])

    for i in range(len(dates)):
        day_desc = weather_code_desc(codes[i]) if i < len(codes) else ""
        lines.append(
            f"  {dates[i]}: {min_temps[i]}-{max_temps[i]}°C, "
            f"{precip[i]}mm rain, {day_desc}"
        )

    lines.append("")
    lines.append("⚠️ *Sangreen Renewables* — Stay safe!")
    return "\n".join(lines)
