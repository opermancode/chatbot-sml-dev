import os
from datetime import datetime
from functools import wraps

from flask import (
    Flask, request, Response, render_template, redirect,
    url_for, flash, jsonify,
)
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from models import db, AdminUser, User, Group, ChatLog, Setting
from twilio.twiml.messaging_response import MessagingResponse
from services.chatbot import handle_incoming, handle_location, log_chat
from services.weather_service import get_weather, format_weather_forecast
from services.twilio_service import send_whatsapp as twilio_send
from services.meta_service import send_whatsapp as meta_send

_basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, instance_path=os.path.join(_basedir, "instance"))
app.config.from_object(Config)
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "admin_login"


@login_manager.user_loader
def load_user(user_id):
    return AdminUser.query.get(int(user_id))


# ─── Helpers ──────────────────────────────────────────────────────────────


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


def get_setting(key, default=""):
    s = Setting.query.filter_by(key=key).first()
    return s.value if s else default


def set_setting(key, value):
    s = Setting.query.filter_by(key=key).first()
    if s:
        s.value = value
    else:
        s = Setting(key=key, value=value)
        db.session.add(s)
    db.session.commit()


def get_app_setting(key, env_fallback=""):
    db_val = get_setting(key)
    if db_val:
        return db_val
    return getattr(Config, env_fallback, "") if env_fallback else ""


def send_provider(to, body):
    provider = get_setting("whatsapp_provider", "twilio")
    if provider == "twilio":
        sid = get_app_setting("twilio_account_sid", "TWILIO_ACCOUNT_SID")
        token = get_app_setting("twilio_auth_token", "TWILIO_AUTH_TOKEN")
        num = get_app_setting("twilio_whatsapp_number", "TWILIO_WHATSAPP_NUMBER")
        return twilio_send(to, body, sid, token, num)
    elif provider == "meta":
        token = get_app_setting("meta_whatsapp_token", "META_WHATSAPP_TOKEN")
        pid = get_app_setting("meta_phone_number_id", "META_PHONE_NUMBER_ID")
        return meta_send(to, body, token, pid)
    else:
        raise ValueError(f"Unknown provider: {provider}")



# ─── Landing Page ─────────────────────────────────────────────────────────

@app.route("/")
def landing():
    return render_template("landing.html")

# ─── Admin Auth ───────────────────────────────────────────────────────────


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        admin = AdminUser.query.filter_by(username=username).first()
        if admin and check_password_hash(admin.password, password):
            login_user(admin)
            next_page = request.args.get("next")
            return redirect(next_page or url_for("admin_dashboard"))
        flash("Invalid credentials", "error")
    return render_template("admin/login.html")


@app.route("/admin/logout")
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for("admin_login"))


# ─── Admin Dashboard ──────────────────────────────────────────────────────


@app.route("/admin")
@admin_required
def admin_dashboard():
    total_users = User.query.count()
    total_chats = ChatLog.query.count()
    today_chats = ChatLog.query.filter(
        db.func.date(ChatLog.created_at) == datetime.utcnow().date()
    ).count()
    total_groups = Group.query.count()
    recent_chats = (
        ChatLog.query.order_by(ChatLog.created_at.desc()).limit(10).all()
    )
    provider = get_setting("whatsapp_provider", "twilio")
    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        total_chats=total_chats,
        today_chats=today_chats,
        total_groups=total_groups,
        recent_chats=recent_chats,
        provider=provider,
    )


# ─── Users ────────────────────────────────────────────────────────────────


@app.route("/admin/users")
@admin_required
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    groups = Group.query.all()
    return render_template("admin/users.html", users=users, groups=groups)


@app.route("/admin/users/add", methods=["POST"])
@admin_required
def admin_users_add():
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    city = request.form.get("city", "").strip()
    site = request.form.get("site", "").strip()
    group_id = request.form.get("group_id") or None

    if not name or not phone:
        flash("Name and phone are required", "error")
        return redirect(url_for("admin_users"))

    if User.query.filter_by(phone=phone).first():
        flash("User with this phone already exists", "error")
        return redirect(url_for("admin_users"))

    phone_clean = phone.replace(" ", "").replace("-", "")
    if not phone_clean.startswith("+"):
        phone_clean = "+91" + phone_clean

    user = User(
        name=name,
        phone=phone_clean,
        city=city,
        site=site,
        group_id=int(group_id) if group_id else None,
    )
    db.session.add(user)
    db.session.commit()
    flash("User added successfully", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/edit/<int:user_id>", methods=["POST"])
@admin_required
def admin_users_edit(user_id):
    user = User.query.get_or_404(user_id)
    user.name = request.form.get("name", user.name).strip()
    user.city = request.form.get("city", user.city).strip()
    user.site = request.form.get("site", user.site).strip()
    group_id = request.form.get("group_id") or None
    user.group_id = int(group_id) if group_id else None
    user.is_active = request.form.get("is_active") == "on"
    db.session.commit()
    flash("User updated", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/delete/<int:user_id>", methods=["POST"])
@admin_required
def admin_users_delete(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash("User deleted", "success")
    return redirect(url_for("admin_users"))


# ─── Groups ───────────────────────────────────────────────────────────────


@app.route("/admin/groups")
@admin_required
def admin_groups():
    groups = Group.query.order_by(Group.created_at.desc()).all()
    return render_template("admin/groups.html", groups=groups)


@app.route("/admin/groups/add", methods=["POST"])
@admin_required
def admin_groups_add():
    name = request.form.get("name", "").strip()
    desc = request.form.get("description", "").strip()
    if not name:
        flash("Group name is required", "error")
        return redirect(url_for("admin_groups"))
    group = Group(name=name, description=desc)
    db.session.add(group)
    db.session.commit()
    flash("Group created", "success")
    return redirect(url_for("admin_groups"))


@app.route("/admin/groups/edit/<int:group_id>", methods=["POST"])
@admin_required
def admin_groups_edit(group_id):
    group = Group.query.get_or_404(group_id)
    group.name = request.form.get("name", group.name).strip()
    group.description = request.form.get("description", "").strip()
    db.session.commit()
    flash("Group updated", "success")
    return redirect(url_for("admin_groups"))


@app.route("/admin/groups/delete/<int:group_id>", methods=["POST"])
@admin_required
def admin_groups_delete(group_id):
    group = Group.query.get_or_404(group_id)
    User.query.filter_by(group_id=group.id).update({User.group_id: None})
    db.session.delete(group)
    db.session.commit()
    flash("Group deleted", "success")
    return redirect(url_for("admin_groups"))


# ─── Broadcast ────────────────────────────────────────────────────────────


@app.route("/admin/broadcast", methods=["GET", "POST"])
@admin_required
def admin_broadcast():
    if request.method == "POST":
        group_id = request.form.get("group_id")
        message = request.form.get("message", "").strip()
        if not message:
            flash("Message is required", "error")
            return redirect(url_for("admin_broadcast"))

        query = User.query.filter_by(is_active=True)
        if group_id:
            query = query.filter_by(group_id=int(group_id))

        users = query.all()
        if not users:
            flash("No users found for broadcast", "error")
            return redirect(url_for("admin_broadcast"))

        sent = 0
        for user in users:
            try:
                send_provider(user.phone, message)
                log_chat(
                    phone=user.phone,
                    message=f"[BROADCAST] {message}",
                    response="Sent",
                    direction="outgoing",
                    message_type="broadcast",
                    user_id=user.id,
                )
                sent += 1
            except Exception as e:
                flash(f"Failed to send to {user.phone}: {e}", "error")

        flash(f"Broadcast sent to {sent}/{len(users)} users", "success")
        return redirect(url_for("admin_broadcast"))

    groups = Group.query.all()
    return render_template("admin/broadcast.html", groups=groups)


# ─── Chat Logs ────────────────────────────────────────────────────────────


@app.route("/admin/chats")
@admin_required
def admin_chats():
    session_id = request.args.get("session_id", type=int)
    search = request.args.get("search", "").strip()

    from services.chatlog_db import get_all_sessions, get_session, get_session_messages

    sessions = get_all_sessions(search)

    messages = []
    selected_session = None
    if session_id:
        selected_session = get_session(session_id)
        if selected_session:
            messages = get_session_messages(session_id)

    return render_template(
        "admin/chats.html",
        sessions=sessions,
        messages=messages,
        selected_session=selected_session,
        search=search,
        enumerate=enumerate,
    )


# ─── Settings ─────────────────────────────────────────────────────────────


@app.route("/admin/settings", methods=["GET", "POST"])
@admin_required
def admin_settings():
    if request.method == "POST":
        for key in request.form:
            if key.startswith("setting_"):
                setting_key = key[8:]
                set_setting(setting_key, request.form[key])

        # Update env vars if provider changes
        provider = request.form.get("setting_whatsapp_provider", "twilio")
        os.environ["WHATSAPP_PROVIDER"] = provider

        flash("Settings saved", "success")
        return redirect(url_for("admin_settings"))

    settings = Setting.query.all()
    settings_dict = {s.key: s.value for s in settings}
    return render_template(
        "admin/settings.html",
        settings=settings_dict,
        env={
            "TWILIO_ACCOUNT_SID": Config.TWILIO_ACCOUNT_SID,
            "TWILIO_AUTH_TOKEN": Config.TWILIO_AUTH_TOKEN,
            "TWILIO_WHATSAPP_NUMBER": Config.TWILIO_WHATSAPP_NUMBER,
            "META_WHATSAPP_TOKEN": Config.META_WHATSAPP_TOKEN,
            "META_PHONE_NUMBER_ID": Config.META_PHONE_NUMBER_ID,
            "META_VERIFY_TOKEN": Config.META_VERIFY_TOKEN,
            "WHATSAPP_PROVIDER": Config.WHATSAPP_PROVIDER,
        },
    )


# ─── Twilio Webhook ───────────────────────────────────────────────────────


@app.route("/webhook/whatsapp", methods=["GET", "POST"])
def webhook_whatsapp():
    # Meta webhook verification
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        expected = get_setting("meta_verify_token", Config.META_VERIFY_TOKEN)
        if mode == "subscribe" and token and token == expected:
            return challenge, 200
        return "Verification failed", 403
    import sys

    phone = request.form.get("From", "").replace("whatsapp:", "").strip()
    if phone and not phone.startswith("+"):
        phone = "+" + phone
    body = request.form.get("Body", "")
    num_media = int(request.form.get("NumMedia", 0))

    lat = request.form.get("Latitude")
    lon = request.form.get("Longitude")

    print(f"[WEBHOOK] phone={phone!r} body={body!r} lat={lat!r} lon={lon!r} num_media={num_media}", file=sys.stderr, flush=True)

    if body.strip() == "test":
        response = f"Test reply at {datetime.now().strftime('%H:%M:%S')}. Your phone: {phone}"
        print(f"[WEBHOOK] test response={response!r}", file=sys.stderr, flush=True)
    elif lat and lon:
        response = handle_location(phone, float(lat), float(lon))
        print(f"[WEBHOOK] location response={response!r}", file=sys.stderr, flush=True)
    elif num_media > 0:
        response = "Thanks for sharing! For weather, please share your live location via the 📍 attachment button."
        print(f"[WEBHOOK] media response={response!r}", file=sys.stderr, flush=True)
    else:
        response = handle_incoming(phone, body)
        print(f"[WEBHOOK] incoming response={response!r}", file=sys.stderr, flush=True)

    if response is None:
        print(f"[WEBHOOK] response is None, returning empty 200", file=sys.stderr, flush=True)
        return "", 200

    print(f"[WEBHOOK] response type={type(response).__name__} len={len(response)}", file=sys.stderr, flush=True)
    twiml = MessagingResponse()
    twiml.message(response)
    twiml_str = str(twiml)
    print(f"[WEBHOOK] twiml length={len(twiml_str)}", file=sys.stderr, flush=True)
    print(f"[WEBHOOK] twiml preview={twiml_str[:200]}", file=sys.stderr, flush=True)
    return twiml_str, 200, {"Content-Type": "text/xml"}


# ─── Init DB ──────────────────────────────────────────────────────────────


@app.cli.command("init-db")
def init_db():
    db.create_all()
    if not AdminUser.query.first():
        admin = AdminUser(
            username=Config.ADMIN_USERNAME,
            password=generate_password_hash(Config.ADMIN_PASSWORD),
        )
        db.session.add(admin)
        db.session.commit()
        print(f"Admin created: {Config.ADMIN_USERNAME}")
    print("Database initialized.")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        if not AdminUser.query.first():
            admin = AdminUser(
                username=Config.ADMIN_USERNAME or "admin",
                password=generate_password_hash(Config.ADMIN_PASSWORD or "changeme123"),
            )
            db.session.add(admin)
            db.session.commit()
    app.run(debug=True, host="0.0.0.0", port=5000)
