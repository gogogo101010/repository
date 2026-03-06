import logging
from flask import Flask
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config
from utils.db import init_db, get_db
from bson import ObjectId

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=Config.RATELIMIT_STORAGE_URI,
    default_limits=["200 per minute"],
)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize database
    init_db(app)

    # Rate limiter
    limiter.init_app(app)

    # Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        from models import User

        db = get_db()
        user_data = db.users.find_one({"_id": ObjectId(user_id)})
        if user_data:
            return User(user_data)
        return None

    # Register blueprints
    from routes.auth import auth_bp
    from routes.customer import customer_bp
    from routes.admin import admin_bp
    from routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(customer_bp, url_prefix="/customer")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(api_bp, url_prefix="/api")

    logger.info("Application started")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
