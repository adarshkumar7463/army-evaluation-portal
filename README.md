# ⚔️ Army Evaluation Portal — Setup & Deployment Guide

## Project Overview
Production-ready Django portal for Army Agniveer evaluation management
with full Role-Based Access Control, multi-evaluator marking, reports, and analytics.

---

## 🚀 Quick Start (Local Development)

### Step 1: Extract & Navigate
```bash
unzip army_portal.zip
cd army_portal
```

### Step 2: Create Virtual Environment
```bash
python -m venv venv

# Linux/Mac:
source venv/bin/activate

# Windows:
venv\Scripts\activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Environment Configuration
Create a `.env` file in the project root:
```env
SECRET_KEY=your-super-secret-key-minimum-50-characters-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

### Step 5: Database Setup
```bash
python manage.py makemigrations accounts
python manage.py makemigrations departments
python manage.py makemigrations evaluation
python manage.py makemigrations logs
python manage.py makemigrations
python manage.py migrate
```

### Step 6: Load Sample Data (Recommended)
```bash
python manage.py setup_portal
```

This creates ALL users and sample data automatically.

### Step 7: Collect Static Files
```bash
python manage.py collectstatic --noinput
```

### Step 8: Run Server
```bash
python manage.py runserver
```

Visit: **http://127.0.0.1:8000/**

---

## 🔐 Default Login Credentials

| Role        | Username    | Password       |
|-------------|-------------|----------------|
| Commander   | commander   | Commander@123  |
| G Head      | ghead       | GHead@123      |
| Dept A      | deptA       | Dept@1234      |
| Dept B      | deptB       | Dept@1234      |
| Dept C      | deptC       | Dept@1234      |
| Dept D      | deptD       | Dept@1234      |
| NCO (A)     | ncoA        | Trainer@123    |
| JCO (A)     | jcoA        | Trainer@123    |
| Officer (A) | officerA    | Trainer@123    |
| NCO (B)     | ncoB        | Trainer@123    |
| JCO (B)     | jcoB        | Trainer@123    |
| Officer (B) | officerB    | Trainer@123    |

---

## 🏗️ Project Structure

```
army_portal/
├── army_portal/          # Main project config
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── accounts/             # Authentication & RBAC
│   ├── models.py         # CustomUser with roles
│   ├── views.py          # Login, logout, user management
│   ├── forms.py          # User creation forms
│   ├── mixins.py         # Role-based access mixins
│   └── urls.py
├── core/                 # Dashboard & home
│   ├── views.py          # Role-specific dashboards
│   ├── context_processors.py
│   └── management/
│       └── commands/
│           └── setup_portal.py  # Sample data loader
├── departments/          # Agniveer management
│   ├── models.py         # Agniveer model
│   ├── views.py          # CRUD operations
│   ├── forms.py
│   └── urls.py
├── evaluation/           # Evaluation system
│   ├── models.py         # EvaluationSheet, Marks
│   ├── views.py          # Marks entry, locking
│   ├── forms.py
│   └── urls.py
├── reports/              # PDF/Excel export
│   ├── views.py          # CSV, Excel, PDF generators
│   └── urls.py
├── logs/                 # Activity tracking
│   ├── models.py         # ActivityLog
│   ├── views.py
│   ├── middleware.py
│   ├── utils.py
│   └── urls.py
├── templates/            # All HTML templates
│   ├── base.html         # Master layout
│   ├── accounts/
│   ├── core/
│   ├── departments/
│   ├── evaluation/
│   ├── reports/
│   └── logs/
├── static/               # CSS, JS, images
├── requirements.txt
└── manage.py
```

---

## 📊 Role-Based Access Control

```
Developer
    └── Commander (Full Access)
            └── G Department Head
                    └── Department A/B/C/D
                            └── Trainers (NCO / JCO / Officer)
                                    └── Evaluate Agniveers
```

### Permissions Matrix

| Feature               | Commander | G Head | Dept | Trainer |
|-----------------------|-----------|--------|------|---------|
| Create G Head         | ✅        | ❌     | ❌   | ❌      |
| Create Dept User      | ✅        | ✅     | ❌   | ❌      |
| Create Trainer        | ✅        | ✅     | ✅   | ❌      |
| Register Agniveer     | ✅        | ✅     | ✅   | ❌      |
| Enter Marks           | ✅        | ✅     | ✅   | ✅      |
| Lock Sheet            | ✅        | ✅     | ✅   | ❌      |
| View All Depts        | ✅        | ✅     | ❌   | ❌      |
| View Activity Logs    | ✅        | ✅     | ❌   | ❌      |
| Export Reports        | ✅        | ✅     | ✅   | ✅      |

---

## 📝 Evaluation System

### Categories & Tests
- **On Field Training:** Physical Test, Weapon Test, Field Training
- **Basic Trade Training:** Assessment, Viva, On Job Training, Written Exam

### Marking Logic
- NCO: 20 marks
- JCO: 20 marks
- Officer: 20 marks
- **Total: 60 marks**
- **Pass: ≥ 30 (50%)**

### Workflow
1. Department creates evaluation sheet
2. NCO enters marks (0–20) → saved
3. JCO enters marks (0–20) → saved
4. Officer enters marks (0–20) → saved
5. Department/Commander locks the sheet
6. Locked sheets generate Pass/Fail result
7. Report card downloadable as PDF

---

## 📦 Export Formats

| Format  | Content                        | URL                              |
|---------|--------------------------------|----------------------------------|
| CSV     | Agniveer list                  | /reports/export/agniveers/csv/   |
| CSV     | Evaluation results             | /reports/export/evaluations/csv/ |
| Excel   | Formatted evaluation report    | /reports/export/evaluations/excel/ |
| PDF     | Individual report card         | /reports/export/report-card/{pk}/pdf/ |
| PDF     | Department summary             | /reports/export/department/{dept}/pdf/ |
| CSV     | Activity logs                  | /logs/export/                    |

---

## 🚀 Production Deployment

### Using Gunicorn + Nginx

```bash
# Install
pip install gunicorn

# Update .env
DEBUG=False
SECRET_KEY=your-strong-production-key
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Run
gunicorn army_portal.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

### Nginx Config
```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location /static/ {
        alias /path/to/army_portal/staticfiles/;
    }

    location /media/ {
        alias /path/to/army_portal/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Switch to PostgreSQL (Production)
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'army_portal_db',
        'USER': 'army_user',
        'PASSWORD': 'strong_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

---

## 🔒 Security Features

- ✅ CSRF Protection (Django default)
- ✅ Session-based authentication
- ✅ Account lockout after 5 failed attempts (30 min)
- ✅ Role-based URL and queryset isolation
- ✅ IP address logging
- ✅ Password hashing (Django PBKDF2)
- ✅ Secure headers (production mode)
- ✅ Evaluation sheet locking (immutable after lock)

---

## 📞 URLs Reference

| URL                        | Description                  |
|----------------------------|------------------------------|
| /                          | Home / Dashboard (redirects) |
| /accounts/login/           | Login page                   |
| /accounts/logout/          | Logout                       |
| /accounts/profile/         | User profile                 |
| /accounts/users/           | User list                    |
| /departments/agniveers/    | Agniveer list                |
| /evaluation/               | Evaluation list              |
| /evaluation/create/        | New evaluation               |
| /evaluation/{id}/marks/    | Marks entry                  |
| /evaluation/report-card/{id}/ | Report card              |
| /reports/                  | Reports dashboard            |
| /logs/                     | Activity logs                |
| /admin/                    | Django admin panel           |
