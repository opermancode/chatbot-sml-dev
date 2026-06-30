import requests

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
        "timezone": "auto",
        "forecast_days": 7,
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
    gust = current.get("wind_gusts_10m")
    wind_dir = current.get("wind_direction_10m")
    wind_label = wind_dir_label(wind_dir)

    wind_10m = current.get("wind_speed_10m", "N/A")
    wind_80m = current.get("wind_speed_80m")
    wind_120m = current.get("wind_speed_120m")
    wind_180m = current.get("wind_speed_180m")

    lines = [
        "🌤 *Live Weather at Your Site*",
        f"Condition: {desc}",
        f"Temperature: {temp}°C",
    ]
    if feels is not None:
        lines.append(f"Feels Like: {feels}°C")
    lines.append(f"Humidity: {humidity}%")
    lines.append(f"Cloud Cover: {cloud}%")
    if rain_chance is not None:
        lines.append(f"Rain Chance: {rain_chance}% "
                      f"({'⚠️' if rain_chance > 60 else '☂️' if rain_chance > 30 else '🌤'})")
    if rain_mm is not None and rain_mm > 0:
        lines.append(f"Rain: {rain_mm} mm")
    lines.append(f"Pressure: {current.get('pressure_msl', 'N/A')} hPa")

    lines.append("")
    lines.append("🌬 *Wind*")
    dir_str = f" ({wind_label})" if wind_label else ""
    lines.append(f"  Direction: {wind_dir}{dir_str}")
    lines.append(f"  At 10m:  {wind_10m} km/h")
    if gust is not None:
        lines.append(f"  Gusts:    {gust} km/h 💨")
    if wind_80m is not None:
        lines.append(f"  At 80m:  {wind_80m} km/h")
    if wind_120m is not None:
        lines.append(f"  At 120m: {wind_120m} km/h")
    if wind_180m is not None:
        lines.append(f"  At 180m: {wind_180m} km/h")

    lines.append("")
    lines.append("⚠️ *Sangreen Renewables* — Stay safe!")
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
        "📅 *7-Day Forecast*",
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
