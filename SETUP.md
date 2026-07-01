# Sangreen Weather Bot — Setup Guide

## Prerequisites

- **Server**: Ubuntu 22.04+ (any VPS or local machine)
- **Twilio account** with WhatsApp Sandbox enabled (free)
- **ngrok account** (free at https://ngrok.com)
- **Python 3.10+** and `pip`

---

## 1. Install system dependencies

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git curl
```

## 2. Clone the repo

```bash
git clone <your-repo-url>
cd weather-chatbot
```

## 3. Set up environment

```bash
cp .env.example .env
nano .env
```

Fill in every field:

| Variable | Description | Example |
|---|---|---|
| `SECRET_KEY` | Random string for Flask sessions | `openssl rand -hex 32` |
| `FLASK_ENV` | Keep `development` | `development` |
| `FLASK_DEBUG` | Keep `1` for now | `1` |
| `DATABASE_URL` | Leave as default (auto-resolved to absolute path) | `sqlite:///chatbot.db` |
| `TWILIO_ACCOUNT_SID` | From Twilio Console → Account → API Credentials | `ACxxxxxxxxxx` |
| `TWILIO_AUTH_TOKEN` | From Twilio Console (same page) | `abc123def456` |
| `TWILIO_WHATSAPP_NUMBER` | Twilio Sandbox number (see WhatsApp → Sandbox) | `+14155238886` |
| `ADMIN_USERNAME` | Your admin login | `admin` |
| `ADMIN_PASSWORD` | Your admin password (change this!) | `your-strong-password` |
| `WHATSAPP_PROVIDER` | Keep `twilio` for now | `twilio` |

> **Note**: `META_*` fields are for future production use — leave them as-is.

## 4. Install Python packages

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

If you get `externally-managed-environment` error (Ubuntu 24.04+):

```bash
pip install --break-system-packages -r requirements.txt
```

## 5. Install & authenticate ngrok

```bash
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install -y ngrok
```

Authenticate your ngrok agent (get the token from https://dashboard.ngrok.com/get-started/your-authtoken):

```bash
ngrok config add-authtoken YOUR_NGROK_AUTHTOKEN
```

## 6. Start the Flask app

```bash
nohup python3 app.py > app.log 2>&1 &
```

Verify it's running:

```bash
curl -s http://localhost:5000/admin/login | head -c 100
# Should return HTML (login page)
```

Check logs if something went wrong:

```bash
tail -20 app.log
```

## 7. Start ngrok

```bash
nohup ngrok http 5000 --log=stdout > ngrok.log 2>&1 &
```

Get your public URL:

```bash
curl -s http://127.0.0.1:4040/api/tunnels | python3 -c "import sys,json; t=json.load(sys.stdin)['tunnels']; print(t[0]['public_url'])"
```

It will look like `https://xxxx-xx-xx-xx-xx.ngrok-free.app`

## 8. Configure Twilio WhatsApp Sandbox

1. Go to **[Twilio Console](https://console.twilio.com)** → **Messaging** → **Try it out** → **Send a WhatsApp message**
2. Under **Sandbox**, note the sandbox number (e.g. `+14155238886`)
3. Set **"When a message comes in"** to:
   ```
   https://your-ngrok-id.ngrok-free.app/webhook/whatsapp
   ```
4. Set **Method** → `HTTP POST`
5. Click **Save**

> ⚠️ If your ngrok URL changes (free tier resets on restart), repeat step 8 with the new URL.

## 9. Create admin user & log in

The first user is created automatically on startup using the credentials from `.env`.

Open your browser:

```
http://<YOUR-SERVER-IP>:5000/admin/login
```

Default: **admin** / **changeme123** (or whatever you set in `.env`)

## 10. Add a WhatsApp user

1. In admin portal → **Users** → **Add User**
2. Fill in:
   - **Name**: e.g. `Omkar`
   - **Phone**: Full number with country code (e.g. `+919146322662`)
   - **City**: e.g. `Pune`
   - **Site**: e.g. `Pune Solar Plant`
   - **Group**: (optional, for broadcasting)
3. Click **Save**

## 11. Test from your phone

1. Open WhatsApp on your phone
2. Send the **join code** (found in Twilio Sandbox page, usually `join <something>`) to the sandbox number (`+14155238866`)
3. Wait for Twilio's confirmation reply
4. Send **"hi"** to the same number
5. You should receive the welcome message with the weather menu

---

## File structure (what's in this repo)

```
weather-chatbot/
├── .env.example           # Template — copy to .env and fill
├── .gitignore
├── app.py                 # Main Flask app with routes
├── config.py              # Config from .env (auto-resolves DB path)
├── models.py              # DB models (User, Group, ChatLog, AdminUser, Setting)
├── requirements.txt       # Python dependencies
├── SETUP.md               # This file
├── services/
│   ├── __init__.py
│   ├── chatbot.py         # Bot state machine, menu logic, geocoding
│   ├── twilio_service.py  # Send WhatsApp via Twilio API
│   └── weather_service.py # Open-Meteo weather (current + hourly forecast, IST tz)
├── templates/
│   └── admin/             # Tailwind HTML templates
│       ├── base.html
│       ├── login.html
│       ├── dashboard.html
│       ├── users.html
│       ├── groups.html
│       ├── broadcast.html
│       ├── chats.html
│       └── settings.html
└── static/                # (empty — templates use Tailwind CDN)
```

---

## Useful commands

| What you want | Command |
|---|---|
| View app logs | `tail -f app.log` |
| View ngrok logs | `tail -f ngrok.log` |
| Restart Flask | `pkill -f "python3 app.py" && nohup python3 app.py > app.log 2>&1 &` |
| Stop ngrok | `pkill ngrok` |
| Open Python shell | `source venv/bin/activate && python3` |
| Check port 5000 | `lsof -i :5000` |
| Get ngrok URL | `curl -s http://127.0.0.1:4040/api/tunnels \| python3 -c "import sys,json;print(json.load(sys.stdin)['tunnels'][0]['public_url'])"` |

---

## Troubleshooting

**App crashes with `PermissionError: '/instance'`**
→ You ran `python3 app.py` from a wrong directory. Always run from the repo root (`~/weather-chatbot`). The config.py now handles this automatically.

**Webhook returns empty 200 / bot doesn't reply**
→ The phone number format might not match. Check the user's phone in admin — must include `+` and country code (e.g. `+919146322662`).

**"User is not registered" even after adding**
→ The user needs to first send the Twilio Sandbox join code to activate their number for the sandbox.

**ngrok URL keeps changing**
→ Free ngrok URLs change on every restart. Upgrade to a paid plan for fixed subdomain, or update the Twilio webhook URL each time.

---

## Next: Switch to Meta Cloud API (Production)

When ready to move to production with a business WhatsApp number:

1. Enter Meta credentials in admin → **Settings**
2. Change **Provider** dropdown from `twilio` to `meta`
3. Click **Save**
4. Update webhook URL in Meta Developer Console to point to your server

No code changes needed — the provider toggle is built in.
