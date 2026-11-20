# Dependency & Security Hardening Documentation

This document records the resolved dependencies, vendored frontend libraries, and security auditing for Hotel Coral Heights Website.

---

## 1. Python Dependencies (`requirements.txt`)
All Python dependencies have been strictly pinned to exact resolved versions:
- `Django==5.2.17`
- `psycopg2-binary==2.9.12`
- `django-environ==0.14.0`
- `django-csp==4.0`
- `whitenoise==6.12.0`
- `weasyprint==69.0`
- `pillow==12.3.0`
- `gunicorn==26.2.0`
- Supporting runtime libraries: `asgiref`, `sqlparse`, `cffi`, `pycparser`, `pydyf`, `pyphen`, `tinycss2`, `tinyhtml5`, `fonttools`, `tzdata`, `brotli`, `zopfli`.

---

## 2. Vendored Frontend Libraries
- **Alpine.js**:
  - **File Path**: `static/vendor/alpine.min.js`
  - **Version**: `3.14.9` (CSP-friendly build)
  - **Integrity**: Vendored locally to avoid external CDN dependencies and satisfy the strict Content Security Policy (`script-src 'self'`).
  - **CSP Restrictions**: Does not evaluate dynamic expressions (eval / Function constructor). All reactive components, getters, and methods are defined in `static/js/main.js` via `Alpine.data()`.

---

## 3. Node & NPM Dependency Audit
- **CSS Toolchain**: Tailwind CSS v3 with PostCSS and Autoprefixer.
- **Audit Fix**:
  - Resolved `postcss-selector-parser <6.1.5` (Quadratic complexity vulnerability).
  - Resolved `source-map-js 1.0.0-1.2.1` (Event loop DoS vulnerability).
  - Audit status: `found 0 vulnerabilities`.
- **CSS Compilation**: Rebuilt with `npm run build:css` -> generated minified `static/css/tailwind.css`.

