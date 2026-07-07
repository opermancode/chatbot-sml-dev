import requests

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
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("messages", [{}])[0].get("id", "")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Meta API error: {e}")
