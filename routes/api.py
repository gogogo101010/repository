import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from utils.db import get_db
from utils.proxmox import proxmox
from utils.bitpay import bitpay
from bson import ObjectId

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__)


@api_bp.route("/bitpay/webhook", methods=["POST"])
def bitpay_webhook():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid payload"}), 400

    invoice_data = data.get("data", {})
    invoice_id = invoice_data.get("id")
    status = invoice_data.get("status")

    if not invoice_id:
        return jsonify({"error": "Missing invoice ID"}), 400

    db = get_db()
    payment = db.payments.find_one({"invoice_id": invoice_id})

    if not payment:
        return jsonify({"error": "Payment not found"}), 404

    # Verify the invoice status directly with BitPay to prevent spoofed webhooks
    try:
        verified_invoice = bitpay.get_invoice(invoice_id)
        verified_status = verified_invoice.get("status")
    except Exception:
        logger.error("Failed to verify BitPay invoice %s", invoice_id)
        return jsonify({"error": "Verification failed"}), 500

    if verified_status in ("confirmed", "complete"):
        db.payments.update_one(
            {"_id": payment["_id"]}, {"$set": {"status": "paid"}}
        )
        logger.info("Payment %s marked as paid (invoice %s)", payment["_id"], invoice_id)

        # If this payment is for a server, update server status
        if payment.get("server_id"):
            db.servers.update_one(
                {"_id": payment["server_id"]},
                {"$set": {"status": "pending_provision"}},
            )

    elif verified_status == "expired":
        db.payments.update_one(
            {"_id": payment["_id"]}, {"$set": {"status": "expired"}}
        )
        logger.info("Payment %s expired (invoice %s)", payment["_id"], invoice_id)

    return jsonify({"status": "ok"}), 200


@api_bp.route("/server/<server_id>/status")
@login_required
def server_status(server_id):
    db = get_db()
    server = db.servers.find_one({"_id": ObjectId(server_id)})

    if not server:
        return jsonify({"error": "Not found"}), 404

    # Verify the requesting user owns this server
    if server["user_id"] != current_user.id and not current_user.is_admin:
        return jsonify({"error": "Access denied"}), 403

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
        logger.warning("Failed to reach VM %s for server %s", server["vm_id"], server_id)
        return jsonify({"status": "unreachable"}), 503
