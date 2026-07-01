from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


class AdminUser(UserMixin, db.Model):
    __tablename__ = "admin_users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)


class Group(db.Model):
    __tablename__ = "groups"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    users = db.relationship("User", backref="group", lazy="dynamic")


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False, index=True)
    city = db.Column(db.String(120), default="")
    site = db.Column(db.String(120), default="")
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    chats = db.relationship("ChatLog", backref="user", lazy="dynamic")

    @property
    def last_chat(self):
        return ChatLog.query.filter_by(user_id=self.id)\
            .order_by(ChatLog.created_at.desc()).first()


class ChatLog(db.Model):
    __tablename__ = "chat_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    phone = db.Column(db.String(20), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, default="")
    direction = db.Column(db.String(10), nullable=False)
    message_type = db.Column(db.String(50), default="text")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Setting(db.Model):
    __tablename__ = "settings"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(120), unique=True, nullable=False)
    value = db.Column(db.Text, default="")
