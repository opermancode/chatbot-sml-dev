# Sangreen Weather Bot — Setup Guide (Ubuntu)

## Prerequisites
- Ubuntu server (22.04+)
- Twilio account (WhatsApp Sandbox)
- ngrok account (free)

---

## 1. Install dependencies

```bash
sudo apt update -y
sudo apt upgrade -y
sudo apt install -y python3 python3-pip git
```

## 2. Clone the project

```bash
git clone <your-repo-url>
cd <repo-name>
```

## 3. Create .env file

```bash
cp .env.example .env
nano .env
```

Set these values:

| Variable | What to put |
|---|---|
| `SECRET_KEY` | Random string (e.g. `openssl rand -hex 32`) |
| `TWILIO_ACCOUNT_SID` | From Twilio Console |
| `TWILIO_AUTH_TOKEN` | From Twilio Console |
| `TWILIO_WHATSAPP_NUMBER` | `+14155238886` (sandbox) |
| `ADMIN_USERNAME` | Your choice |
| `ADMIN_PASSWORD` | Your choice |

## 4. Install Python packages

```bash
pip3 install --break-system-packages -r requirements.txt
```

## 5. Install ngrok

```bash
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install -y ngrok
```

## 6. Start the app

```bash
nohup python3 app.py > app.log 2>&1 &
```

Check it's running:
```bash
curl http://localhost:5000/admin/login
# Should return HTML (login page)
```

## 7. Start ngrok

```bash
nohup ngrok http 5000 > ngrok.log 2>&1 &
```

Get the ngrok URL:
```bash
curl -s http://127.0.0.1:4040/api/tunnels | python3 -c "import sys,json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])"
```

## 8. Configure Twilio

1. Go to [Twilio Console](https://console.twilio.com) → WhatsApp → Sandbox
2. Set **"When a message comes in"** to:
   ```
   https://your-ngrok-id.ngrok-free.dev/webhook/whatsapp
   ```
3. Set **Method** to `HTTP POST`
4. Save

## 9. Log in to admin

```
http://<YOUR-EC2-PUBLIC-IP>:5000/admin
```

Default: `admin` / `changeme123` (or whatever you set in `.env`)

## 10. Add users & test

1. In admin → **Users** → **Add User**
2. Enter name and phone (with country code, e.g. `+919876543210`)
3. Save
4. From your phone, WhatsApp the Twilio sandbox number (`+14155238886`) with the join code
5. Then send "Hi" — you'll get the welcome message

---

## Useful commands

| Command | What it does |
|---|---|
| `tail -f app.log` | Watch app logs |
| `tail -f ngrok.log` | Watch ngrok logs |
| `pkill -f "python3 app.py"` | Stop Flask |
| `pkill ngrok` | Stop ngrok |
| `lsof -i :5000` | Check if port 5000 is in use |

## Switch to Meta (later)

1. Get Meta credentials (see admin Settings page)
2. Enter them in admin → Settings
3. Change provider dropdown to `Meta`
4. Save — no code changes needed
