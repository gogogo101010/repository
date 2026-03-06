from flask_login import UserMixin
from datetime import datetime, timezone


# --- Status Constants ---

class ServerStatus:
    PROVISIONING = "provisioning"
    PENDING_PROVISION = "pending_provision"
    ACTIVE = "active"
    EXPIRED = "expired"
    PURGED = "purged"


class PaymentStatus:
    PENDING = "pending"
    PAID = "paid"
    EXPIRED = "expired"


class TicketStatus:
    OPEN = "open"
    CLOSED = "closed"
    WAITING = "waiting"


class TicketPriority:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# --- Models ---


class User(UserMixin):
    def __init__(self, data):
        self.data = data
        self.id = str(data["_id"])
        self.email = data.get("email", "")
        self.name = data.get("name", "")
        self.is_admin = data.get("is_admin", False)
        self.suspended = data.get("suspended", False)
        self.created_at = data.get("created_at", datetime.now(timezone.utc))

    @property
    def is_active(self):
        return not self.suspended


def new_user(name, email, password_hash):
    return {
        "name": name,
        "email": email,
        "password": password_hash,
        "is_admin": False,
        "suspended": False,
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
        "status": ServerStatus.PROVISIONING,
        "cores": plan_data["cores"],
        "ram": plan_data["ram"],
        "disk": plan_data["disk"],
        "bandwidth": plan_data["bandwidth"],
        "price": plan_data["price"],
        "created_at": datetime.now(timezone.utc),
        "expires_at": None,
    }


def new_ticket(user_id, subject, message, priority=TicketPriority.MEDIUM):
    return {
        "user_id": user_id,
        "subject": subject,
        "status": TicketStatus.OPEN,
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
        "status": PaymentStatus.PENDING,
        "payment_url": None,
        "created_at": datetime.now(timezone.utc),
    }
