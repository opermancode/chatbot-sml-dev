from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from config import Config


def get_client(account_sid=None, auth_token=None):
    sid = account_sid or Config.TWILIO_ACCOUNT_SID
    token = auth_token or Config.TWILIO_AUTH_TOKEN
    return Client(sid, token)


def send_whatsapp(to: str, body: str, account_sid=None, auth_token=None,
                  from_number=None):
    client = get_client(account_sid, auth_token)
    sender = from_number or Config.TWILIO_WHATSAPP_NUMBER
    try:
        message = client.messages.create(
            body=body,
            from_=f"whatsapp:{sender}",
            to=f"whatsapp:{to}",
        )
        return message.sid
    except TwilioRestException as e:
        raise Exception(f"Twilio error: {e}")
