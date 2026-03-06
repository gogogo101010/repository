from flask import Blueprint, request, jsonify
from utils.db import get_db
from utils.proxmox import proxmox

api_bp = Blueprint("api", __name__)


@api_bp.route("/bitpay/webhook", methods=["POST"])
def bitpay_webhook():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid payload"}), 400

    event = data.get("event", {})
    invoice_data = data.get("data", {})
    invoice_id = invoice_data.get("id")
    status = invoice_data.get("status")

    if not invoice_id:
        return jsonify({"error": "Missing invoice ID"}), 400

    db = get_db()
    payment = db.payments.find_one({"invoice_id": invoice_id})

    if not payment:
        return jsonify({"error": "Payment not found"}), 404

    if status == "confirmed" or status == "complete":
        db.payments.update_one(
            {"_id": payment["_id"]}, {"$set": {"status": "paid"}}
        )

        # If this payment is for a server, update server status
        if payment.get("server_id"):
            db.servers.update_one(
                {"_id": payment["server_id"]},
                {"$set": {"status": "pending_provision"}},
            )

    elif status == "expired":
        db.payments.update_one(
            {"_id": payment["_id"]}, {"$set": {"status": "expired"}}
        )

    return jsonify({"status": "ok"}), 200


@api_bp.route("/server/<server_id>/status")
def server_status(server_id):
    from flask_login import current_user, login_required
    from bson import ObjectId

    db = get_db()
    server = db.servers.find_one({"_id": ObjectId(server_id)})

    if not server:
        return jsonify({"error": "Not found"}), 404

    if not server.get("vm_id"):
        return jsonify({"status": server.get("status", "unknown")})

    try:
        vm_status = proxmox.get_vm_status(server["vm_id"])
        return jsonify(
            {
                "status": vm_status.get("status", "unknown"),
                "cpu": vm_status.get("cpu", 0),
                "mem": vm_status.get("mem", 0),
                "maxmem": vm_status.get("maxmem", 0),
                "uptime": vm_status.get("uptime", 0),
                "netin": vm_status.get("netin", 0),
                "netout": vm_status.get("netout", 0),
            }
        )
    except Exception:
        return jsonify({"status": "unreachable"}), 503
