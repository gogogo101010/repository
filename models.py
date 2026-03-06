from flask_login import UserMixin
from datetime import datetime, timezone


class User(UserMixin):
    def __init__(self, data):
        self.data = data
        self.id = str(data["_id"])
        self.email = data.get("email", "")
        self.name = data.get("name", "")
        self.is_admin = data.get("is_admin", False)
        self.created_at = data.get("created_at", datetime.now(timezone.utc))


def new_user(name, email, password_hash):
    return {
        "name": name,
        "email": email,
        "password": password_hash,
        "is_admin": False,
        "balance": 0.00,
        "created_at": datetime.now(timezone.utc),
    }


def new_server(user_id, plan_id, plan_data, hostname, iso, vm_id=None):
    return {
        "user_id": user_id,
        "plan_id": plan_id,
        "hostname": hostname,
        "iso": iso,
        "vm_id": vm_id,
        "ip_address": None,
        "status": "provisioning",
        "cores": plan_data["cores"],
        "ram": plan_data["ram"],
        "disk": plan_data["disk"],
        "bandwidth": plan_data["bandwidth"],
        "price": plan_data["price"],
        "created_at": datetime.now(timezone.utc),
        "expires_at": None,
    }


def new_ticket(user_id, subject, message, priority="medium"):
    return {
        "user_id": user_id,
        "subject": subject,
        "status": "open",
        "priority": priority,
        "messages": [
            {
                "sender": "customer",
                "message": message,
                "created_at": datetime.now(timezone.utc),
            }
        ],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


def new_payment(user_id, amount, description, server_id=None):
    return {
        "user_id": user_id,
        "amount": amount,
        "description": description,
        "server_id": server_id,
        "invoice_id": None,
        "status": "pending",
        "payment_url": None,
        "created_at": datetime.now(timezone.utc),
    }
