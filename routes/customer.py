from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from utils.db import get_db
from utils.proxmox import proxmox
from utils.bitpay import bitpay
from models import new_server, new_ticket, new_payment
from config import Config
from bson import ObjectId
from datetime import datetime, timezone

customer_bp = Blueprint("customer", __name__)


@customer_bp.before_request
@login_required
def require_login():
    pass


@customer_bp.route("/")
def dashboard():
    db = get_db()
    servers = list(db.servers.find({"user_id": current_user.id}))
    tickets = list(
        db.tickets.find({"user_id": current_user.id}).sort("updated_at", -1).limit(5)
    )
    payments = list(
        db.payments.find({"user_id": current_user.id}).sort("created_at", -1).limit(5)
    )
    return render_template(
        "customer/dashboard.html",
        servers=servers,
        tickets=tickets,
        payments=payments,
    )


# --- Servers ---


@customer_bp.route("/servers")
def servers():
    db = get_db()
    servers = list(db.servers.find({"user_id": current_user.id}))
    return render_template("customer/servers.html", servers=servers)


@customer_bp.route("/servers/order", methods=["GET", "POST"])
def order_server():
    if request.method == "POST":
        db = get_db()
        plan_id = request.form.get("plan")
        hostname = request.form.get("hostname", "").strip()
        iso = request.form.get("iso", "")

        if plan_id not in Config.PLANS:
            flash("Invalid plan selected.", "error")
            return redirect(url_for("customer.order_server"))

        if not hostname:
            flash("Hostname is required.", "error")
            return redirect(url_for("customer.order_server"))

        plan = Config.PLANS[plan_id]

        # Create payment first
        payment_data = new_payment(
            current_user.id, plan["price"], f"Server order - {plan['name']} plan"
        )
        payment_result = db.payments.insert_one(payment_data)

        # Create server record
        server_data = new_server(current_user.id, plan_id, plan, hostname, iso)
        server_data["payment_id"] = str(payment_result.inserted_id)
        server_result = db.servers.insert_one(server_data)

        # Update payment with server reference
        db.payments.update_one(
            {"_id": payment_result.inserted_id},
            {"$set": {"server_id": str(server_result.inserted_id)}},
        )

        # Create BitPay invoice
        try:
            invoice = bitpay.create_invoice(
                amount=plan["price"],
                order_id=str(payment_result.inserted_id),
                redirect_url=f"https://{Config.DOMAIN}/customer/servers",
                notification_url=f"https://{Config.DOMAIN}/api/bitpay/webhook",
            )
            db.payments.update_one(
                {"_id": payment_result.inserted_id},
                {
                    "$set": {
                        "invoice_id": invoice.get("id"),
                        "payment_url": invoice.get("url"),
                    }
                },
            )
            if invoice.get("url"):
                return redirect(invoice["url"])
        except Exception:
            # If BitPay fails, mark as pending manual review
            flash(
                "Payment gateway temporarily unavailable. Your order has been recorded and will be processed shortly.",
                "warning",
            )

        return redirect(url_for("customer.servers"))

    return render_template(
        "customer/order_server.html",
        plans=Config.PLANS,
        isos=Config.DEFAULT_ISOS,
    )


@customer_bp.route("/servers/<server_id>")
def server_detail(server_id):
    db = get_db()
    server = db.servers.find_one(
        {"_id": ObjectId(server_id), "user_id": current_user.id}
    )
    if not server:
        flash("Server not found.", "error")
        return redirect(url_for("customer.servers"))

    # Get VM status from Proxmox
    vm_status = None
    if server.get("vm_id"):
        try:
            vm_status = proxmox.get_vm_status(server["vm_id"])
        except Exception:
            vm_status = None

    # Get snapshots
    snapshots = []
    if server.get("vm_id"):
        try:
            snapshots = proxmox.list_snapshots(server["vm_id"]) or []
        except Exception:
            snapshots = []

    # Get backups
    backups = []
    if server.get("vm_id"):
        try:
            backups = proxmox.list_backups(server["vm_id"]) or []
        except Exception:
            backups = []

    return render_template(
        "customer/server_detail.html",
        server=server,
        vm_status=vm_status,
        snapshots=snapshots,
        backups=backups,
        plans=Config.PLANS,
    )


@customer_bp.route("/servers/<server_id>/action", methods=["POST"])
def server_action(server_id):
    db = get_db()
    server = db.servers.find_one(
        {"_id": ObjectId(server_id), "user_id": current_user.id}
    )
    if not server or not server.get("vm_id"):
        flash("Server not found.", "error")
        return redirect(url_for("customer.servers"))

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
        elif action == "purge":
            confirm = request.form.get("confirm_purge")
            if confirm != server.get("hostname"):
                flash("Hostname confirmation does not match. Server not purged.", "error")
            else:
                proxmox.delete_vm(vm_id)
                db.servers.update_one(
                    {"_id": ObjectId(server_id)},
                    {"$set": {"status": "purged", "vm_id": None}},
                )
                flash("Server has been purged.", "success")
                return redirect(url_for("customer.servers"))
        else:
            flash("Unknown action.", "error")
    except Exception as e:
        flash(f"Action failed: {str(e)}", "error")

    return redirect(url_for("customer.server_detail", server_id=server_id))


@customer_bp.route("/servers/<server_id>/snapshot", methods=["POST"])
def create_snapshot(server_id):
    db = get_db()
    server = db.servers.find_one(
        {"_id": ObjectId(server_id), "user_id": current_user.id}
    )
    if not server or not server.get("vm_id"):
        flash("Server not found.", "error")
        return redirect(url_for("customer.servers"))

    name = request.form.get("snapshot_name", "").strip()
    description = request.form.get("snapshot_description", "").strip()

    if not name:
        flash("Snapshot name is required.", "error")
        return redirect(url_for("customer.server_detail", server_id=server_id))

    try:
        proxmox.create_snapshot(server["vm_id"], name, description)
        flash("Snapshot created successfully.", "success")
    except Exception as e:
        flash(f"Failed to create snapshot: {str(e)}", "error")

    return redirect(url_for("customer.server_detail", server_id=server_id))


@customer_bp.route("/servers/<server_id>/snapshot/<snapname>/delete", methods=["POST"])
def delete_snapshot(server_id, snapname):
    db = get_db()
    server = db.servers.find_one(
        {"_id": ObjectId(server_id), "user_id": current_user.id}
    )
    if not server or not server.get("vm_id"):
        flash("Server not found.", "error")
        return redirect(url_for("customer.servers"))

    try:
        proxmox.delete_snapshot(server["vm_id"], snapname)
        flash("Snapshot deleted.", "success")
    except Exception as e:
        flash(f"Failed to delete snapshot: {str(e)}", "error")

    return redirect(url_for("customer.server_detail", server_id=server_id))


@customer_bp.route("/servers/<server_id>/backup", methods=["POST"])
def create_backup(server_id):
    db = get_db()
    server = db.servers.find_one(
        {"_id": ObjectId(server_id), "user_id": current_user.id}
    )
    if not server or not server.get("vm_id"):
        flash("Server not found.", "error")
        return redirect(url_for("customer.servers"))

    try:
        proxmox.create_backup(server["vm_id"])
        flash("Backup started. It may take a few minutes to complete.", "success")
    except Exception as e:
        flash(f"Failed to create backup: {str(e)}", "error")

    return redirect(url_for("customer.server_detail", server_id=server_id))


@customer_bp.route("/servers/<server_id>/upgrade", methods=["GET", "POST"])
def upgrade_server(server_id):
    db = get_db()
    server = db.servers.find_one(
        {"_id": ObjectId(server_id), "user_id": current_user.id}
    )
    if not server:
        flash("Server not found.", "error")
        return redirect(url_for("customer.servers"))

    if request.method == "POST":
        new_plan_id = request.form.get("plan")
        if new_plan_id not in Config.PLANS:
            flash("Invalid plan.", "error")
            return redirect(
                url_for("customer.upgrade_server", server_id=server_id)
            )

        new_plan = Config.PLANS[new_plan_id]
        current_plan = Config.PLANS.get(server["plan_id"], {})
        price_diff = new_plan["price"] - current_plan.get("price", 0)

        if price_diff <= 0:
            flash("You can only upgrade to a higher plan.", "error")
            return redirect(
                url_for("customer.upgrade_server", server_id=server_id)
            )

        # Create upgrade payment
        payment_data = new_payment(
            current_user.id,
            price_diff,
            f"Upgrade from {current_plan.get('name', 'N/A')} to {new_plan['name']}",
            str(server["_id"]),
        )
        payment_result = db.payments.insert_one(payment_data)

        try:
            invoice = bitpay.create_invoice(
                amount=price_diff,
                order_id=str(payment_result.inserted_id),
                redirect_url=f"https://{Config.DOMAIN}/customer/servers/{server_id}",
                notification_url=f"https://{Config.DOMAIN}/api/bitpay/webhook",
            )
            db.payments.update_one(
                {"_id": payment_result.inserted_id},
                {
                    "$set": {
                        "invoice_id": invoice.get("id"),
                        "payment_url": invoice.get("url"),
                    }
                },
            )
            if invoice.get("url"):
                return redirect(invoice["url"])
        except Exception:
            flash("Payment gateway temporarily unavailable.", "warning")

        return redirect(url_for("customer.server_detail", server_id=server_id))

    return render_template(
        "customer/upgrade_server.html",
        server=server,
        plans=Config.PLANS,
    )


# --- Tickets ---


@customer_bp.route("/tickets")
def tickets():
    db = get_db()
    tickets = list(
        db.tickets.find({"user_id": current_user.id}).sort("updated_at", -1)
    )
    return render_template("customer/tickets.html", tickets=tickets)


@customer_bp.route("/tickets/new", methods=["GET", "POST"])
def new_ticket_page():
    if request.method == "POST":
        db = get_db()
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()
        priority = request.form.get("priority", "medium")

        if not subject or not message:
            flash("Subject and message are required.", "error")
            return render_template("customer/new_ticket.html")

        ticket_data = new_ticket(current_user.id, subject, message, priority)
        db.tickets.insert_one(ticket_data)
        flash("Ticket created successfully.", "success")
        return redirect(url_for("customer.tickets"))

    return render_template("customer/new_ticket.html")


@customer_bp.route("/tickets/<ticket_id>", methods=["GET", "POST"])
def ticket_detail(ticket_id):
    db = get_db()
    ticket = db.tickets.find_one(
        {"_id": ObjectId(ticket_id), "user_id": current_user.id}
    )
    if not ticket:
        flash("Ticket not found.", "error")
        return redirect(url_for("customer.tickets"))

    if request.method == "POST":
        message = request.form.get("message", "").strip()
        if message:
            db.tickets.update_one(
                {"_id": ObjectId(ticket_id)},
                {
                    "$push": {
                        "messages": {
                            "sender": "customer",
                            "message": message,
                            "created_at": datetime.now(timezone.utc),
                        }
                    },
                    "$set": {
                        "updated_at": datetime.now(timezone.utc),
                        "status": "open",
                    },
                },
            )
            flash("Reply sent.", "success")
            return redirect(url_for("customer.ticket_detail", ticket_id=ticket_id))

    return render_template("customer/ticket_detail.html", ticket=ticket)


# --- Payments ---


@customer_bp.route("/payments")
def payments():
    db = get_db()
    payments = list(
        db.payments.find({"user_id": current_user.id}).sort("created_at", -1)
    )
    return render_template("customer/payments.html", payments=payments)
