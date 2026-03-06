# VPS Hosting Platform

A web-based VPS hosting platform built with Flask that allows customers to order, manage, and pay for virtual private servers. Servers are provisioned and managed via the Proxmox virtualization API, with payments handled through BitPay cryptocurrency gateway.

## Features

- **User Authentication** — Registration, login, session management with bcrypt password hashing
- **Server Management** — Order servers from 4 tiers, manage lifecycle (start/stop/reboot/shutdown/purge)
- **Snapshots & Backups** — Create, list, and delete VM snapshots and backups
- **Server Upgrades** — Upgrade between plans with prorated pricing
- **Support Tickets** — Customer-admin messaging system with priority levels
- **Payments** — BitPay cryptocurrency invoice creation and webhook processing
- **Admin Dashboard** — Statistics, server provisioning, IP management, ticket/payment/user management

## Tech Stack

- **Backend:** Flask 3.0, Python
- **Database:** MongoDB (pymongo)
- **Cache:** Redis
- **Virtualization:** Proxmox VE (via REST API)
- **Payments:** BitPay API
- **Auth:** Flask-Login, bcrypt, Flask-WTF (CSRF)
- **Server:** Gunicorn

## Server Plans

| Plan | vCPUs | RAM | Disk | Bandwidth | Price |
|------|-------|-----|------|-----------|-------|
| Starter | 1 | 1 GB | 20 GB | 1 TB | $5/mo |
| Basic | 2 | 2 GB | 40 GB | 2 TB | $10/mo |
| Standard | 4 | 4 GB | 80 GB | 4 TB | $20/mo |
| Premium | 8 | 8 GB | 160 GB | 8 TB | $40/mo |

## Setup

### Prerequisites

- Python 3.10+
- MongoDB
- Redis
- Proxmox VE host (for VM provisioning)
- BitPay API key (for payments)

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd repository
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. Create an admin user:
   ```bash
   python create_admin.py
   ```

5. Run the application:
   ```bash
   # Development
   python app.py

   # Production
   gunicorn app:create_app() -b 0.0.0.0:5000
   ```

## Project Structure

```
app.py                  # Flask app factory and blueprint registration
config.py               # Configuration, server plans, and ISO definitions
models.py               # Data models (User, Server, Ticket, Payment)
create_admin.py         # Utility to create admin users
requirements.txt        # Python dependencies
routes/
  auth.py               # Authentication (login, register, logout)
  customer.py           # Customer dashboard, server/ticket/payment management
  admin.py              # Admin panel
  api.py                # REST API (BitPay webhook, server status)
utils/
  db.py                 # MongoDB and Redis initialization
  proxmox.py            # Proxmox API client
  bitpay.py             # BitPay payment client
templates/
  base.html             # Base layout template
  index.html            # Home page
  faq.html              # FAQ page
  auth/                 # Login and registration templates
  customer/             # Customer dashboard templates
  admin/                # Admin panel templates
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key for sessions | `dev-secret-key` |
| `MONGO_URI` | MongoDB connection string | `mongodb://localhost:27017/servers_com` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `PROXMOX_HOST` | Proxmox API URL | `https://localhost:8006` |
| `PROXMOX_USER` | Proxmox username | `root@pam` |
| `PROXMOX_PASSWORD` | Proxmox password | — |
| `PROXMOX_NODE` | Proxmox node name | `pve` |
| `BITPAY_API_KEY` | BitPay API key | — |
| `BITPAY_API_URL` | BitPay API base URL | `https://bitpay.com/api` |
| `DOMAIN` | Application domain | `servers.com` |

## Supported OS Images

Ubuntu 22.04 LTS, Ubuntu 24.04 LTS, Debian 12, CentOS Stream 9, Rocky Linux 9, AlmaLinux 9, Windows Server 2022
