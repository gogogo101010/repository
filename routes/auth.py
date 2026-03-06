import logging
import secrets
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from utils.db import get_db, get_redis
from models import User, new_user
from datetime import datetime, timezone, timedelta
import bcrypt

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/")
def index():
    return render_template("index.html")


@auth_bp.route("/faq")
def faq():
    return render_template("faq.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        db = get_db()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user_data = db.users.find_one({"email": email})
        if user_data and bcrypt.checkpw(
            password.encode("utf-8"), user_data["password"]
        ):
            user = User(user_data)
            if user.suspended:
                flash("Your account has been suspended. Please contact support.", "error")
                return render_template("auth/login.html")
            login_user(user)
            logger.info("User %s logged in", user.id)
            if user.is_admin:
                return redirect(url_for("admin.dashboard"))
            return redirect(url_for("customer.dashboard"))
        logger.warning("Failed login attempt for email: %s", email)
        flash("Invalid email or password.", "error")
    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        db = get_db()
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not name or not email or not password:
            flash("All fields are required.", "error")
            return render_template("auth/register.html")

        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("auth/register.html")

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("auth/register.html")

        if db.users.find_one({"email": email}):
            flash("Email already registered.", "error")
            return render_template("auth/register.html")

        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        user_data = new_user(name, email, hashed)
        result = db.users.insert_one(user_data)
        user_data["_id"] = result.inserted_id

        user = User(user_data)
        login_user(user)
        logger.info("New user registered: %s (id: %s)", email, user.id)
        return redirect(url_for("customer.dashboard"))

    return render_template("auth/register.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        db = get_db()
        redis_client = get_redis()
        email = request.form.get("email", "").strip().lower()

        user_data = db.users.find_one({"email": email})
        if user_data:
            token = secrets.token_urlsafe(32)
            # Store reset token in Redis with 1-hour expiry
            redis_client.setex(f"password_reset:{token}", 3600, str(user_data["_id"]))
            logger.info("Password reset requested for %s (token generated)", email)
            # In production, send this via email. For now, log it.
            logger.info("Password reset link: /reset-password/%s", token)

        # Always show success to prevent email enumeration
        flash("If an account with that email exists, a password reset link has been sent.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    redis_client = get_redis()
    user_id = redis_client.get(f"password_reset:{token}")

    if not user_id:
        flash("Invalid or expired reset link.", "error")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        db = get_db()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("auth/reset_password.html", token=token)

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("auth/reset_password.html", token=token)

        from bson import ObjectId

        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"password": hashed}},
        )

        # Delete the token so it can't be reused
        redis_client.delete(f"password_reset:{token}")

        logger.info("Password reset completed for user %s", user_id)
        flash("Password has been reset. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", token=token)
