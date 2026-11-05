# Hotel Coral Heights — Web Application

Hotel Coral Heights is a full-featured web application and booking platform built with Django, Vanilla CSS / Tailwind CSS, and Alpine.js.

## Key Architecture & Asset Decisions

### 1. `static/css/tailwind.css` (Compiled Stylesheet)
- The application utilizes Tailwind CSS alongside custom architectural styling in `static/css/main.css`.
- Source styles reside in `src/input.css` and are compiled into `static/css/tailwind.css`.
- **Deployment Build Step**: At deploy time, run:
  ```bash
  npm run build:css
  ```
  This minifies and rebuilds `static/css/tailwind.css` to match all template utility classes.

### 2. `staticfiles/` (Static Assets Distribution)
- Always run `npm run build:css` before `collectstatic`.
- Django's `collectstatic` gathers all static assets from `static/` into `staticfiles/`:
  ```bash
  python manage.py collectstatic --noinput
  ```
- In production, WhiteNoise serves compressed and cache-manifested static assets directly from `staticfiles/`.
- `staticfiles/` is an ephemeral build artifact and is ignored by version control.

### 3. `media/` (User & Dynamic Content Storage)
- The `media/` directory contains user-uploaded dynamic content such as room photography, attraction gallery items, and receipt files.
- WhiteNoise only serves static files from `staticfiles/`. Uploaded dynamic files under `/media/` must be served directly by Nginx in production.
- **Nginx Media Serving Example**:
  ```nginx
  client_max_body_size 10M;

  location /media/ {
      alias /path/to/media/;
  }
  ```
- **Data Persistence & Backups**: `media/` contains live user data that must be backed up separately via object storage (e.g. AWS S3, Cloudflare R2) or persistent volumes.
- `media/` must **never** be packaged into source code release zips or committed to version control.

---

## Production Deployment Guide

### 1. Ubuntu System Prerequisites (for WeasyPrint PDF Receipts)
WeasyPrint requires native system libraries for HTML/CSS to PDF rendering (Pango, Cairo, and GDK-PixBuf). On Ubuntu 22.04 / 24.04:
```bash
sudo apt-get update && sudo apt-get install -y \
  libpango-1.0-0 \
  libpangoft2-1.0-0 \
  libpangocairo-1.0-0 \
  libcairo2 \
  libgdk-pixbuf-2.0-0 \
  libffi-dev \
  shared-mime-info
```

### 2. Deployment Steps (Run in Order)
1. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
2. **Install Node dependencies & build Tailwind CSS**:
   ```bash
   npm ci
   npm run build:css
   ```
3. **Run database migrations**:
   ```bash
   python manage.py migrate
   ```
4. **Create database cache table** (required for OTP rate-limiting across multi-worker Gunicorn):
   ```bash
   python manage.py createcachetable
   ```
5. **Collect static assets**:
   ```bash
   python manage.py collectstatic --noinput
   ```
6. **Restart Gunicorn service**:
   ```bash
   sudo systemctl restart coralheights
   ```

### 3. Gunicorn & Nginx Reverse Proxy Setup
Run Gunicorn using the WSGI entrypoint:
```bash
gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3
```

In your Nginx server block:
```nginx
server {
    server_name demo.example.com;

    client_max_body_size 10M;

    location /media/ {
        alias /path/to/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
> **CRITICAL**: `proxy_set_header X-Forwarded-Proto $scheme;` must be passed so Django detects HTTPS behind the reverse proxy. Missing this header will trigger an infinite redirect loop when `SECURE_SSL_REDIRECT=True`.

### 4. Deployment Check (`python manage.py check --deploy`)
Running `python manage.py check --deploy` in production validates security settings. The only expected warning on initial demo deployment is:
- `security.W021` (`SECURE_HSTS_PRELOAD` not set to True): This is intentional. HSTS preload is difficult to undo once submitted to browser lists. Preload and higher HSTS durations (`SECURE_HSTS_SECONDS=31536000`) should only be enabled once HTTPS is confirmed stable on the final production domain.

---

## Local Development Setup

1. **Install Python Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Install Node Dependencies & Build CSS**:
   ```bash
   npm install
   npm run build:css
   ```

3. **Configure Environment Variables**:
   Copy `.env.example` to `.env` and set:
   - `DEBUG=True`
   - `SECRET_KEY=...` (in production, a strong non-default secret key is mandatory; missing keys raise `ImproperlyConfigured` when `DEBUG=False`)
   - `ALLOW_MOCK_PAYMENT=True` (only for development/testing environments; MockPaymentGateway raises `ImproperlyConfigured` if `DEBUG=False` without explicit opt-in)
   - `DATABASE_URL=...` (PostgreSQL recommended; SQLite fallback for local development)

4. **Apply Database Migrations & Run**:
   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

5. **Run Test Suite**:
   ```bash
   python manage.py test
   ```
