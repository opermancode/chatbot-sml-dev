import re
from models import db, User, ChatLog
from services.weather_service import get_weather, format_current_weather

def welcome_msg(name: str):
    return f"""🌤 *Welcome to Sangreen Renewables Weather Bot!*

👋 Hello {name}!

We provide real-time weather updates for your work sites.

Choose an option:
1️⃣ *Current Weather* — Share your live location to get weather
2️⃣ *About Sangreen* — Learn about us
3️⃣ *Contact Support* — Talk to our team

Reply with the number of your choice."""

ABOUT_MSG = """🌿 *Sangreen Renewables*

We are a renewable energy company dedicated to sustainable power solutions across India.

🌱 Solar | 💨 Wind | 💧 Hydro
🔋 Energy Storage | ⚡ EPC Services

*Our Mission:* Powering a greener tomorrow.

Reply *0* to go back to main menu."""

CONTACT_MSG = """📞 *Sangreen Renewables Support*

📍 Head Office: [Your Office Address]
📧 Email: support@sangreenrenewables.com
📱 Phone: [Your Contact Number]

Reply *0* to go back to main menu."""

LOCATION_PROMPT = """📍 *Share Your Location*

Please share your live location to get real-time weather for your current site.

📱 *How to share location on WhatsApp:*
1. Tap the 📎 (attachment) icon
2. Select *Location*
3. Tap *Share Live Location* or *Send Your Current Location*

Once you share, I'll fetch the weather forecast!"""


def get_or_create_user(phone: str):
    user = User.query.filter_by(phone=phone).first()
    return user


def log_chat(phone: str, message: str, response: str, direction: str,
             message_type: str = "text", user_id=None):
    chat = ChatLog(
        user_id=user_id,
        phone=phone,
        message=message,
        response=response,
        direction=direction,
        message_type=message_type,
    )
    db.session.add(chat)
    db.session.commit()


def handle_incoming(phone: str, message: str):
    user = get_or_create_user(phone)
    user_id = user.id if user else None

    if not user:
        return None

    msg = message.strip().lower()

    if msg in ("hi", "hello", "hey", "0", "menu", "main menu"):
        resp = welcome_msg(user.name)
        log_chat(phone, message, resp, "outgoing", user_id=user_id)
        return resp

    if msg == "1":
        log_chat(phone, message, LOCATION_PROMPT, "outgoing", user_id=user_id)
        return LOCATION_PROMPT

    if msg == "2":
        log_chat(phone, message, ABOUT_MSG, "outgoing", user_id=user_id)
        return ABOUT_MSG

    if msg == "3":
        log_chat(phone, message, CONTACT_MSG, "outgoing", user_id=user_id)
        return CONTACT_MSG

    text = (
        "I didn't understand that. Reply with:\n"
        "1️⃣ Current Weather\n"
        "2️⃣ About Sangreen\n"
        "3️⃣ Contact Support\n"
        "0️⃣ Main Menu"
    )
    log_chat(phone, message, text, "outgoing", user_id=user_id)
    return text


def handle_location(phone: str, lat: float, lon: float) -> str:
    user = get_or_create_user(phone)
    user_id = user.id if user else None

    data = get_weather(lat, lon)
    weather = format_current_weather(data)

    log_chat(
        phone,
        f"Location shared: {lat},{lon}",
        weather,
        "outgoing",
        message_type="location",
        user_id=user_id,
    )
    return weather + "\n\nReply *0* for main menu."