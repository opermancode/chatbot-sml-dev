import os
from dotenv import load_dotenv

load_dotenv()


_basedir = os.path.dirname(os.path.abspath(__file__))

def _resolve_db_url(url):
    if url and url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
        rel = url[len("sqlite:///"):]
        return f"sqlite:///{os.path.join(_basedir, 'instance', rel)}"
    return url

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = _resolve_db_url(
        os.getenv("DATABASE_URL", "sqlite:///chatbot.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False

    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "")

    META_WHATSAPP_TOKEN = os.getenv("META_WHATSAPP_TOKEN", "")
    META_PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID", "")
    META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "")

    WHATSAPP_PROVIDER = os.getenv("WHATSAPP_PROVIDER", "twilio")

    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme123")
