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
- **Data Persistence & Backups**: `media/` contains live user data that must be backed up separately via object storage (e.g. AWS S3, Cloudflare R2) or persistent volumes.
- `media/` must **never** be packaged into source code release zips or committed to version control.

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
