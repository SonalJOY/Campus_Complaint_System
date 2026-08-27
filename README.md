# Campus Complaint & Maintenance Management System

A college academic project built with Python and Django to manage and track campus infrastructure and facility complaints from submission to resolution with strict Role-Based Access Control (RBAC) and audit trails.

## Technology Stack
- **Backend:** Python 3, Django
- **Database:** SQLite (Development)
- **Frontend:** Bootstrap 5, Vanilla JavaScript, Chart.js
- **Architecture:** Clean Django Monolith

## System Actors & Roles
1. **STUDENT:** Reports issues, tracks complaint status history, and verifies/closes resolved issues.
2. **STAFF:** Receives assigned work orders, updates status to `IN_PROGRESS`, and resolves tickets with remarks.
3. **ADMIN:** Manages categories, assigns incoming tickets to maintenance staff, and reviews analytics.

## Status State Machine
```
[SUBMITTED]  -->  [ASSIGNED]  -->  [IN_PROGRESS]  -->  [RESOLVED]  -->  [CLOSED]
  (Student)         (Admin)           (Staff)           (Staff)      (Student/Admin)
```

## Quick Start
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run migrations
python manage.py migrate

# 3. Start development server
python manage.py runserver
```
