"""Create an admin user. Run this once after setting up the database."""
import sys
import bcrypt
from pymongo import MongoClient
from config import Config
from datetime import datetime, timezone


def create_admin(email, password, name="Admin"):
    client = MongoClient(Config.MONGO_URI)
    db = client.get_default_database()

    if db.users.find_one({"email": email}):
        print(f"User {email} already exists.")
        existing = db.users.find_one({"email": email})
        if not existing.get("is_admin"):
            db.users.update_one({"email": email}, {"$set": {"is_admin": True}})
            print("Updated to admin.")
        return

    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    db.users.insert_one(
        {
            "name": name,
            "email": email,
            "password": hashed,
            "is_admin": True,
            "balance": 0.00,
            "created_at": datetime.now(timezone.utc),
        }
    )
    print(f"Admin user {email} created.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python create_admin.py <email> <password> [name]")
        sys.exit(1)

    email = sys.argv[1]
    password = sys.argv[2]
    name = sys.argv[3] if len(sys.argv) > 3 else "Admin"
    create_admin(email, password, name)
