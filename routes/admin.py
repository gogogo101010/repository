import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from utils.db import get_db
from utils.proxmox import proxmox
from bson import ObjectId
from datetime import datetime, timezone
from functools import wraps

logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__)

PER_PAGE = 20


def paginate(query, page):
    return query.skip((page - 1) * PER_PAGE).limit(PER_PAGE)


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash("Access denied.", "error")
            return redirect(url_for("customer.dashboard"))
        return f(*args, **kwargs)

    return decorated


def attach_users(db, records, user_id_field="user_id"):
    """Batch-load user info for a list of records to avoid N+1 queries."""
    user_ids = list({ObjectId(r[user_id_field]) for r in records if r.get(user_id_field)})
    if not user_ids:
        return
    users_map = {
        str(u["_id"]): u
        for u in db.users.find({"_id": {"$in": user_ids}}, {"name": 1, "email": 1})
    }
    for record in records:
        record["user"] = users_map.get(record.get(user_id_field))


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
    attach_users(db, recent_tickets)

    return render_template(
        "admin/dashboard.html", stats=stats, recent_tickets=recent_tickets
    )


# --- Servers ---


@admin_bp.route("/servers")
@admin_required
def servers():
    db = get_db()
    page = request.args.get("page", 1, type=int)
    total = db.servers.count_documents({})
    servers = list(
        paginate(db.servers.find().sort("created_at", -1), page)
    )
    attach_users(db, servers)

    return render_template(
        "admin/servers.html",
        servers=servers,
        page=page,
        total_pages=(total + PER_PAGE - 1) // PER_PAGE,
    )


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
            logger.warning("Failed to get VM status for server %s", server_id)
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

        from datetime import timedelta

        db.servers.update_one(
            {"_id": ObjectId(server_id)},
            {
                "$set": {
                    "vm_id": int(vmid),
                    "status": "active",
                    "expires_at": datetime.now(timezone.utc) + timedelta(days=30),
                }
            },
        )
        logger.info("Admin %s provisioned server %s with VMID %s", current_user.id, server_id, vmid)
        flash(f"Server provisioned with VMID {vmid}.", "success")
    except Exception:
        logger.exception("Provisioning failed for server %s", server_id)
        flash("Provisioning failed. Check logs for details.", "error")

    return redirect(url_for("admin.server_detail", server_id=server_id))


@admin_bp.route("/servers/<server_id>/action", methods=["POST"])
@admin_required
def server_action(server_id):
    db = get_db()
    server = db.servers.find_one({"_id": ObjectId(server_id)})
    if not server or not server.get("vm_id"):
        flash("Server not found or not provisioned.", "error")
        return redirect(url_for("admin.servers"))

    action = request.form.get("action")
    vm_id = server["vm_id"]

    try:
        if action == "start":
            proxmox.start_vm(vm_id)
            flash("Server is starting.", "success")
        elif action == "shutdown":
            proxmox.shutdown_vm(vm_id)
            flash("Server is shutting down.", "success")
        elif action == "reboot":
            proxmox.reboot_vm(vm_id)
            flash("Server is rebooting.", "success")
        elif action == "stop":
            proxmox.stop_vm(vm_id)
            flash("Server has been stopped.", "success")
        else:
            flash("Unknown action.", "error")
        logger.info("Admin %s performed '%s' on server %s", current_user.id, action, server_id)
    except Exception:
        logger.exception("Admin server action '%s' failed for server %s", action, server_id)
        flash("Server action failed. Check logs for details.", "error")

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
    page = request.args.get("page", 1, type=int)
    status_filter = request.args.get("status", "")
    query = {}
    if status_filter:
        query["status"] = status_filter

    total = db.tickets.count_documents(query)
    tickets = list(
        paginate(db.tickets.find(query).sort("updated_at", -1), page)
    )
    attach_users(db, tickets)

    return render_template(
        "admin/tickets.html",
        tickets=tickets,
        status_filter=status_filter,
        page=page,
        total_pages=(total + PER_PAGE - 1) // PER_PAGE,
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
    page = request.args.get("page", 1, type=int)
    total = db.payments.count_documents({})
    payments = list(
        paginate(db.payments.find().sort("created_at", -1), page)
    )
    attach_users(db, payments)

    return render_template(
        "admin/payments.html",
        payments=payments,
        page=page,
        total_pages=(total + PER_PAGE - 1) // PER_PAGE,
    )


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

    logger.info("Admin %s marked payment %s as paid", current_user.id, payment_id)
    flash("Payment marked as paid.", "success")
    return redirect(url_for("admin.payments"))


# --- Users ---


@admin_bp.route("/users")
@admin_required
def users():
    db = get_db()
    page = request.args.get("page", 1, type=int)
    search = request.args.get("q", "").strip()
    query = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
        ]

    total = db.users.count_documents(query)
    users = list(
        paginate(db.users.find(query).sort("created_at", -1), page)
    )
    return render_template(
        "admin/users.html",
        users=users,
        search=search,
        page=page,
        total_pages=(total + PER_PAGE - 1) // PER_PAGE,
    )


@admin_bp.route("/users/<user_id>/toggle-suspend", methods=["POST"])
@admin_required
def toggle_suspend(user_id):
    db = get_db()
    user = db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("admin.users"))

    new_status = not user.get("suspended", False)
    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"suspended": new_status}},
    )

    action = "suspended" if new_status else "unsuspended"
    logger.info("Admin %s %s user %s", current_user.id, action, user_id)
    flash(f"User {action}.", "success")
    return redirect(url_for("admin.users"))
