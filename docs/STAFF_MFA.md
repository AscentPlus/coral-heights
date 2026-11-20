# Privileged Staff Multi-Factor Authentication (MFA) Setup Guide

This document details the architecture, configuration steps, and operational guidelines for deploying Multi-Factor Authentication (MFA / 2FA) across all privileged staff accounts for Hotel Coral Heights.

---

## 1. Architecture & Strategy

Privileged staff accounts have access to sensitive guest personal data, reservations, room inventory, and website management. To secure these administrative interfaces, MFA can be enabled through either:

1. **Application-Layer TOTP (Time-Based One-Time Password)**
   - Recommended library: `django-otp` with `django-otp-plugins` (`otp-totp`, `otp-static` for backup recovery codes).
   - Staff use standard authenticator apps: Google Authenticator, Microsoft Authenticator, Apple Passwords, or 1Password.

2. **Network/Identity Provider Boundary (SSO / Cloudflare Access / Google Workspace SAML)**
   - Protects the `/staff/` route behind an external zero-trust identity provider with hardware security keys (FIDO2/WebAuthn) or enforced institutional MFA.

---

## 2. Enabling Application-Layer TOTP in Django

When the hotel management approves application-level TOTP rollout, the following configuration steps are required:

### Step 2.1: Dependencies
Add to `requirements.txt`:
```txt
django-otp>=1.5.0
qrcode>=7.4.2
```

### Step 2.2: Django Settings (`config/settings.py`)
```python
INSTALLED_APPS = [
    ...
    'django_otp',
    'django_otp.plugins.otp_totp',
    'django_otp.plugins.otp_static',
    ...
]

MIDDLEWARE = [
    ...
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    ...
]
```

### Step 2.3: Enforcing MFA on Staff Views
In `staff_panel/permissions.py`, wrap `staff_login_required`:
```python
from django_otp.decorators import otp_required

def privileged_staff_required(view_func):
    """Enforces active authenticated session with verified OTP device for privileged operations."""
    return staff_login_required(otp_required(view_func))
```

---

## 3. Enrolment & Recovery Workflow

1. **Staff Onboarding**:
   - The hotel IT administrator or General Manager provisions the staff account in `/staff/manage-staff/`.
   - On initial login, the staff member is redirected to `/staff/profile/mfa/setup/` to scan the TOTP QR code.
2. **Emergency Recovery Codes**:
   - A batch of 5 single-use static recovery tokens is generated and displayed once to the staff member.
   - The staff member must store these offline in the hotel safe or an encrypted password manager.
3. **Lost Device Protocol**:
   - Only a Superuser can revoke a staff member's registered TOTP device from the Django admin or staff management panel.
   - Upon revocation, the staff member must re-enrol upon their next sign-in.

---

## 4. Pending Hotel Configuration Decisions

Before activating enforced MFA in production, the following hotel inputs are required:
- [ ] Confirm whether staff will use personal/work smartphones for authenticator apps.
- [ ] Designate the primary administrator authorized to reset lost 2FA devices and issue emergency bypasses.
- [ ] Confirm if physical hardware security keys (YubiKeys) are required for superusers.

