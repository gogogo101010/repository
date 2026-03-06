import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/servers_com")
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    PROXMOX_HOST = os.getenv("PROXMOX_HOST", "https://localhost:8006")
    PROXMOX_USER = os.getenv("PROXMOX_USER", "root@pam")
    PROXMOX_PASSWORD = os.getenv("PROXMOX_PASSWORD", "")
    PROXMOX_NODE = os.getenv("PROXMOX_NODE", "pve")

    BITPAY_API_KEY = os.getenv("BITPAY_API_KEY", "")
    BITPAY_API_URL = os.getenv("BITPAY_API_URL", "https://bitpay.com/api")

    DOMAIN = os.getenv("DOMAIN", "servers.com")

    # Server plans
    PLANS = {
        "starter": {
            "name": "Starter",
            "cores": 1,
            "ram": 1024,
            "disk": 20,
            "bandwidth": 1000,
            "price": 5.00,
        },
        "basic": {
            "name": "Basic",
            "cores": 2,
            "ram": 2048,
            "disk": 40,
            "bandwidth": 2000,
            "price": 10.00,
        },
        "standard": {
            "name": "Standard",
            "cores": 4,
            "ram": 4096,
            "disk": 80,
            "bandwidth": 4000,
            "price": 20.00,
        },
        "premium": {
            "name": "Premium",
            "cores": 8,
            "ram": 8192,
            "disk": 160,
            "bandwidth": 8000,
            "price": 40.00,
        },
    }

    # Default ISOs
    DEFAULT_ISOS = [
        {"id": "ubuntu-22.04", "name": "Ubuntu 22.04 LTS", "file": "ubuntu-22.04-live-server-amd64.iso"},
        {"id": "ubuntu-24.04", "name": "Ubuntu 24.04 LTS", "file": "ubuntu-24.04-live-server-amd64.iso"},
        {"id": "debian-12", "name": "Debian 12", "file": "debian-12-amd64-netinst.iso"},
        {"id": "centos-9", "name": "CentOS Stream 9", "file": "CentOS-Stream-9-latest-x86_64-dvd1.iso"},
        {"id": "rocky-9", "name": "Rocky Linux 9", "file": "Rocky-9-latest-x86_64-dvd.iso"},
        {"id": "almalinux-9", "name": "AlmaLinux 9", "file": "AlmaLinux-9-latest-x86_64-dvd.iso"},
        {"id": "windows-2022", "name": "Windows Server 2022", "file": "windows-server-2022.iso"},
    ]
