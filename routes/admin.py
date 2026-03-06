from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from utils.db import get_db
from utils.proxmox import proxmox
from bson import ObjectId
from datetime import datetime, timezone
from functools import wraps

admin_bp = Blueprint("admin", __name__)


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash("Access denied.", "error")
            return redirect(url_for("customer.dashboard"))
        return f(*args, **kwargs)

    return decorated


@admin_bp.route("/")
@admin_required
def dashboard():
    db = get_db()
    stats = {
        "total_servers": db.servers.count_documents({}),
        "active_servers": db.servers.count_documents({"status": "active"}),
        "total_users": db.users.count_documents({}),
        "open_tickets": db.tickets.count_documents({"status": "open"}),
        "total_revenue": sum(
            p.get("amount", 0)
            for p in db.payments.find({"status": "paid"}, {"amount": 1})
        ),
    }
    recent_tickets = list(db.tickets.find().sort("updated_at", -1).limit(10))

    # Attach user info to tickets
    for ticket in recent_tickets:
        user = db.users.find_one(
            {"_id": ObjectId(ticket["user_id"])}, {"name": 1, "email": 1}
        )
        ticket["user"] = user

    return render_template(
        "admin/dashboard.html", stats=stats, recent_tickets=recent_tickets
    )


# --- Servers ---


@admin_bp.route("/servers")
@admin_required
def servers():
    db = get_db()
    servers = list(db.servers.find().sort("created_at", -1))

    for server in servers:
        user = db.users.find_one(
            {"_id": ObjectId(server["user_id"])}, {"name": 1, "email": 1}
        )
        server["user"] = user

    return render_template("admin/servers.html", servers=servers)


@admin_bp.route("/servers/<server_id>")
@admin_required
def server_detail(server_id):
    db = get_db()
    server = db.servers.find_one({"_id": ObjectId(server_id)})
    if not server:
        flash("Server not found.", "error")
        return redirect(url_for("admin.servers"))

    user = db.users.find_one(
        {"_id": ObjectId(server["user_id"])}, {"name": 1, "email": 1}
    )
    server["user"] = user

    vm_status = None
    if server.get("vm_id"):
        try:
            vm_status = proxmox.get_vm_status(server["vm_id"])
        except Exception:
            vm_status = None

    return render_template(
        "admin/server_detail.html", server=server, vm_status=vm_status
    )


@admin_bp.route("/servers/<server_id>/provision", methods=["POST"])
@admin_required
def provision_server(server_id):
    db = get_db()
    server = db.servers.find_one({"_id": ObjectId(server_id)})
    if not server:
        flash("Server not found.", "error")
        return redirect(url_for("admin.servers"))

    try:
        vmid = proxmox.get_next_vmid()
        iso_file = ""
        from config import Config

        for iso in Config.DEFAULT_ISOS:
            if iso["id"] == server.get("iso"):
                iso_file = iso["file"]
                break

        proxmox.create_vm(
            vmid=vmid,
            name=server["hostname"],
            cores=server["cores"],
            memory=server["ram"],
            disk_size=server["disk"],
            iso=iso_file,
        )

        # Get assigned IP (from DHCP — will be available after VM boots)
        db.servers.update_one(
            {"_id": ObjectId(server_id)},
            {"$set": {"vm_id": int(vmid), "status": "active"}},
        )
        flash(f"Server provisioned with VMID {vmid}.", "success")
    except Exception as e:
        flash(f"Provisioning failed: {str(e)}", "error")

    return redirect(url_for("admin.server_detail", server_id=server_id))


@admin_bp.route("/servers/<server_id>/update-ip", methods=["POST"])
@admin_required
def update_server_ip(server_id):
    db = get_db()
    ip = request.form.get("ip_address", "").strip()
    db.servers.update_one(
        {"_id": ObjectId(server_id)}, {"$set": {"ip_address": ip}}
    )
    flash("IP address updated.", "success")
    return redirect(url_for("admin.server_detail", server_id=server_id))


# --- Tickets ---


@admin_bp.route("/tickets")
@admin_required
def tickets():
    db = get_db()
    status_filter = request.args.get("status", "")
    query = {}
    if status_filter:
        query["status"] = status_filter

    tickets = list(db.tickets.find(query).sort("updated_at", -1))

    for ticket in tickets:
        user = db.users.find_one(
            {"_id": ObjectId(ticket["user_id"])}, {"name": 1, "email": 1}
        )
        ticket["user"] = user

    return render_template(
        "admin/tickets.html", tickets=tickets, status_filter=status_filter
    )


@admin_bp.route("/tickets/<ticket_id>", methods=["GET", "POST"])
@admin_required
def ticket_detail(ticket_id):
    db = get_db()
    ticket = db.tickets.find_one({"_id": ObjectId(ticket_id)})
    if not ticket:
        flash("Ticket not found.", "error")
        return redirect(url_for("admin.tickets"))

    user = db.users.find_one(
        {"_id": ObjectId(ticket["user_id"])}, {"name": 1, "email": 1}
    )
    ticket["user"] = user

    if request.method == "POST":
        message = request.form.get("message", "").strip()
        new_status = request.form.get("status", "")

        updates = {"$set": {"updated_at": datetime.now(timezone.utc)}}

        if message:
            updates["$push"] = {
                "messages": {
                    "sender": "admin",
                    "message": message,
                    "created_at": datetime.now(timezone.utc),
                }
            }

        if new_status:
            updates["$set"]["status"] = new_status

        db.tickets.update_one({"_id": ObjectId(ticket_id)}, updates)
        flash("Ticket updated.", "success")
        return redirect(url_for("admin.ticket_detail", ticket_id=ticket_id))

    return render_template("admin/ticket_detail.html", ticket=ticket)


# --- Payments ---


@admin_bp.route("/payments")
@admin_required
def payments():
    db = get_db()
    payments = list(db.payments.find().sort("created_at", -1))

    for payment in payments:
        user = db.users.find_one(
            {"_id": ObjectId(payment["user_id"])}, {"name": 1, "email": 1}
        )
        payment["user"] = user

    return render_template("admin/payments.html", payments=payments)


@admin_bp.route("/payments/<payment_id>/mark-paid", methods=["POST"])
@admin_required
def mark_paid(payment_id):
    db = get_db()
    db.payments.update_one(
        {"_id": ObjectId(payment_id)}, {"$set": {"status": "paid"}}
    )

    payment = db.payments.find_one({"_id": ObjectId(payment_id)})
    if payment and payment.get("server_id"):
        db.servers.update_one(
            {"_id": ObjectId(payment["server_id"])},
            {"$set": {"status": "pending_provision"}},
        )

    flash("Payment marked as paid.", "success")
    return redirect(url_for("admin.payments"))


# --- Users ---


@admin_bp.route("/users")
@admin_required
def users():
    db = get_db()
    users = list(db.users.find().sort("created_at", -1))
    return render_template("admin/users.html", users=users)
