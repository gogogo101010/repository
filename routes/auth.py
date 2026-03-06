from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from utils.db import get_db
from models import User, new_user
import bcrypt

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
            login_user(user)
            if user.is_admin:
                return redirect(url_for("admin.dashboard"))
            return redirect(url_for("customer.dashboard"))
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
        return redirect(url_for("customer.dashboard"))

    return render_template("auth/register.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
