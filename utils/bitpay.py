import requests
from config import Config


class BitPayClient:
    def __init__(self):
        self.api_key = Config.BITPAY_API_KEY
        self.api_url = Config.BITPAY_API_URL

    def create_invoice(self, amount, currency="USD", order_id=None, redirect_url=None, notification_url=None):
        headers = {
            "Content-Type": "application/json",
            "X-Accept-Version": "2.0.0",
        }

        if self.api_key:
            headers["Authorization"] = f"Basic {self.api_key}"

        payload = {
            "price": amount,
            "currency": currency,
            "token": self.api_key,
        }

        if order_id:
            payload["orderId"] = order_id
        if redirect_url:
            payload["redirectURL"] = redirect_url
        if notification_url:
            payload["notificationURL"] = notification_url

        resp = requests.post(
            f"{self.api_url}/invoices",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json().get("data", resp.json())

    def get_invoice(self, invoice_id):
        headers = {
            "Content-Type": "application/json",
            "X-Accept-Version": "2.0.0",
        }

        if self.api_key:
            headers["Authorization"] = f"Basic {self.api_key}"

        resp = requests.get(
            f"{self.api_url}/invoices/{invoice_id}",
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json().get("data", resp.json())


bitpay = BitPayClient()
