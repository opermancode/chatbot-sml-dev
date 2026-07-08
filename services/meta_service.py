import requests
import json

META_API_BASE = "https://graph.facebook.com/v21.0"


def send_whatsapp(to: str, body: str, access_token=None,
                  phone_number_id=None):
    token = access_token
    pid = phone_number_id
    if not token or not pid:
        raise ValueError("Meta access_token and phone_number_id are required")

    url = f"{META_API_BASE}/{pid}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    return _post(url, headers, payload)


def send_template(to: str, template_name: str, lang_code: str = "en",
                  body_params: list[str] | None = None,
                  access_token=None, phone_number_id=None):
    token = access_token
    pid = phone_number_id
    if not token or not pid:
        raise ValueError("Meta access_token and phone_number_id are required")

    url = f"{META_API_BASE}/{pid}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    template = {
        "name": template_name,
        "language": {"code": lang_code},
    }
    if body_params:
        template["components"] = [
            {
                "type": "body",
                "parameters": [{"type": "text", "text": p} for p in body_params],
            }
        ]
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": template,
    }
    return _post(url, headers, payload)


def _post(url, headers, payload):
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("messages", [{}])[0].get("id", "")
    except requests.exceptions.RequestException as e:
        detail = ""
        try:
            detail = f": {resp.text}"
        except Exception:
            pass
        raise Exception(f"Meta API error{e}")
