# Project Analysis: VPS Hosting Platform

## Overview

This is a Flask-based VPS hosting platform that allows customers to order, manage, and pay for virtual private servers provisioned via Proxmox. The application includes user authentication, server lifecycle management, a support ticket system, BitPay cryptocurrency payments, and an admin dashboard.

**Tech Stack:** Flask, MongoDB (pymongo), Redis, Proxmox API, BitPay API, bcrypt, Jinja2 templates, Gunicorn

---

## What's Currently Implemented

- **Authentication**: Registration, login, logout with bcrypt password hashing and Flask-Login sessions
- **Server Management**: 4 plans (Starter $5/mo, Basic $10/mo, Standard $20/mo, Premium $40/mo)
- **Server Actions**: Start, stop, shutdown, reboot, purge (with hostname confirmation), upgrade
- **Snapshots & Backups**: Create/list/delete snapshots and backups via Proxmox API
- **Payments**: BitPay crypto payment integration with webhook for invoice status updates
- **Support Tickets**: Customer creates tickets, admin replies, status tracking (open/closed)
- **Admin Panel**: Dashboard stats, server provisioning, IP management, ticket/payment/user management
- **Database**: MongoDB with indexes on users.email, servers.user_id, servers.vm_id, tickets.user_id, payments.user_id, payments.invoice_id

---

## Security Issues (Critical Priority)

### 1. Unauthenticated API Endpoint
**Location:** `routes/api.py:48-76`

The `/api/server/<server_id>/status` endpoint has no authentication or authorization. Anyone can query the status of any server by ID.

**Fix:** Add `@login_required` decorator and verify `current_user.id == server["user_id"]`.

### 2. BitPay Webhook Has No Signature Verification
**Location:** `routes/api.py:8-45`

The webhook endpoint accepts any POST payload without verifying it came from BitPay. An attacker could send fake "confirmed" status updates to mark payments as paid and trigger server provisioning.

**Fix:** Validate the webhook signature using BitPay's HMAC headers or verify the invoice status by calling the BitPay API before processing.

### 3. Exception Details Leaked to Users
**Location:** `routes/customer.py:203`, `routes/customer.py:229`, `routes/customer.py:248`, `routes/customer.py:267`

Error messages like `flash(f"Action failed: {str(e)}", "error")` expose internal details (stack traces, API errors, infrastructure info) to end users.

**Fix:** Show generic error messages to users. Log the full exception server-side.

### 4. SSL Verification Disabled on Proxmox API
**Location:** `utils/proxmox.py:22,38,46` — all requests use `verify=False`

This makes the application vulnerable to man-in-the-middle attacks between the web server and the Proxmox hypervisor.

**Fix:** Make SSL verification configurable via environment variable. Use proper CA certificates in production.

### 5. No Rate Limiting
Login, registration, and API endpoints have no rate limiting, making them vulnerable to brute-force attacks.

**Fix:** Add `flask-limiter` with Redis backend (Redis is already initialized but unused).

### 6. No Input Sanitization
Hostname and snapshot names from user input are passed directly to the Proxmox API without validation.

**Fix:** Validate hostname format (alphanumeric + hyphens, max length). Sanitize snapshot names.

### 7. Weak Default Secret Key
**Location:** `config.py:8`

The Flask secret key falls back to `"dev-secret-key"` if the environment variable is not set. This makes session cookies predictable and forgeable.

**Fix:** Raise an error if `SECRET_KEY` is not set in the environment, rather than using a fallback.

---

## Missing Infrastructure

### 1. No Tests
There are zero test files in the repository. No testing framework is configured.

**Recommendation:** Add `pytest` with fixtures for:
- Unit tests for models and utility functions
- Integration tests for routes (using Flask test client)
- Mocked Proxmox and BitPay API tests

### 2. No CI/CD Pipeline
No GitHub Actions, GitLab CI, or any automated pipeline exists.

**Recommendation:** Add a GitHub Actions workflow for:
- Linting (flake8/ruff)
- Running tests
- Security scanning (bandit)

### 3. No Docker Setup
No Dockerfile or docker-compose configuration.

**Recommendation:** Add:
- `Dockerfile` for the Flask application
- `docker-compose.yml` with services for Flask app, MongoDB, and Redis

### 4. No Logging
There is no logging anywhere in the application. All errors are caught and only displayed via flash messages.

**Recommendation:** Configure Python's `logging` module with structured output. Log all Proxmox API calls, payment events, authentication attempts, and errors.

### 5. Empty README
The README.md file is blank — no setup instructions, architecture overview, or usage documentation.

### 6. No Code Quality Tools
No linting (flake8, ruff), formatting (black), or import sorting (isort) configuration.

---

## Missing Features

### High Priority
| Feature | Details |
|---------|---------|
| **Password reset** | No forgot password or reset flow exists |
| **User profile/settings** | No way to change name, email, or password after registration |
| **Server renewal/expiration** | The `expires_at` field exists in the server model but is never set or checked. No renewal payment flow |
| **Pagination** | All list views (`/customer/servers`, `/admin/users`, etc.) load all records at once. Will break at scale |
| **Admin server actions** | Admin can provision and update IP, but cannot start/stop/reboot customer servers |

### Medium Priority
| Feature | Details |
|---------|---------|
| **Email notifications** | No emails sent for: registration, payment confirmation, ticket replies, server provisioned/expiring |
| **VNC/Console access** | `proxmox.get_vm_vnc()` is implemented in the utility but no route or template uses it |
| **Server reinstall/rebuild** | No option to reinstall the OS on an existing server |
| **User suspension/ban** | No way for admin to disable a user account |
| **Search functionality** | No search on admin pages (servers, users, tickets, payments) |
| **Invoice/receipt generation** | No downloadable invoices for payments |

### Lower Priority
| Feature | Details |
|---------|---------|
| **Two-factor authentication** | No 2FA support |
| **Multiple payment methods** | Only BitPay (crypto). No Stripe, PayPal, or credit card |
| **Bandwidth monitoring** | Bandwidth field exists in server plans but is never tracked or alerted on |
| **API documentation** | No documentation for the API endpoints |

---

## Code Quality Improvements

### 1. Redis is Initialized but Unused
**Location:** `utils/db.py:23`

Redis client is created on startup but never referenced anywhere in the application.

**Use it for:** Session storage, rate limiting backend, caching Proxmox API responses, or remove it.

### 2. No Status Enums/Constants
Server statuses (`provisioning`, `active`, `pending_provision`, `purged`), payment statuses (`pending`, `paid`, `expired`), and ticket statuses (`open`, `closed`) are raw strings scattered throughout the code.

**Fix:** Define constants or Python enums to prevent typos and centralize status management.

### 3. N+1 Query Problem in Admin Views
**Location:** `routes/admin.py:61-65`, `routes/admin.py:160-166`, `routes/admin.py:221-225`

Admin list views loop through records and make individual MongoDB lookups for each user.

**Fix:** Use MongoDB aggregation `$lookup` pipeline to join user data in a single query.

### 4. Broken `download_backup` Method
**Location:** `utils/proxmox.py:138-142`

This method creates local variables (`url`, `headers`, `cookies`) but ignores them and just returns a URL string. It's dead/incomplete code.

### 5. Bare `except Exception` Blocks
Multiple locations catch all exceptions silently, hiding real errors and making debugging difficult.

**Fix:** Catch specific exceptions, log the details, and re-raise or handle appropriately.

### 6. No Request Validation Framework
Form inputs are validated inline with ad-hoc checks. No structured validation.

**Fix:** Use WTForms (already have flask-wtf installed) or marshmallow for consistent input validation.

---

## Summary Priority Matrix

| Priority | Category | Items |
|----------|----------|-------|
| **P0 - Critical** | Security | Unauthenticated API, webhook verification, leaked exceptions, weak secret key |
| **P1 - High** | Security + Infra | Rate limiting, input sanitization, SSL verification, logging, tests |
| **P2 - Medium** | Features | Password reset, server expiration, pagination, email notifications, VNC access |
| **P3 - Low** | Quality + Features | Status enums, N+1 queries, Docker, CI/CD, 2FA, multi-payment |
