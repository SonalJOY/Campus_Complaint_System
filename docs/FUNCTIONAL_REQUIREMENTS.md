# Functional & Non-Functional Requirements Specification (SRS)
## Campus Infrastructure Complaint & Resolution System

This document maps all Functional Requirements (FR1–FR6) and Non-Functional Requirements (NFR1–NFR5) to their architectural design, implementation files, and automated verification suites.

---

## 1. Functional Requirements Matrix

### [FR1] User Authentication & Role-Based Access Control (RBAC)
- **Description**: Secure registration for students and multi-role authentication supporting three distinct roles: `STUDENT`, `STAFF`, and `ADMIN`.
- **Key Capabilities**:
  - Student self-registration with automatic role enforcement to `STUDENT`.
  - Dual-identifier login allowing users to authenticate via either **username** or **email address**.
  - Password hashing utilizing Django's PBKDF2 with SHA-256 algorithm.
  - Centralized role-checking view decorators (`@role_required`, `@student_required`, `@staff_required`, `@admin_required`).
  - Automatic post-login redirection based on user role (`/dashboard/admin/`, `/dashboard/staff/`, `/complaints/dashboard/`).
  - Graceful rejection of deactivated accounts and generic credential validation error messages to prevent username enumeration.
- **Implementation Mapping**:
  - Models: [`accounts/models.py:Profile`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/accounts/models.py)
  - Views: [`accounts/views.py:login_view`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/accounts/views.py), [`register_view`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/accounts/views.py), [`logout_view`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/accounts/views.py)
  - Security Decorators: [`accounts/decorators.py:role_required`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/accounts/decorators.py)
  - Verification: [`accounts/tests.py:AuthenticationAndRBACTests`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/accounts/tests.py) (14 unit tests)

---

### [FR2] Complaint Submission & Classification (Student Portal)
- **Description**: Enables registered students to report campus infrastructure breakdown with rich metadata and optional photographic evidence.
- **Key Capabilities**:
  - Automatic generation of unique sequential ticket identifiers formatted as `CMP-XXXXXX` (e.g. `CMP-000001`).
  - Selection from active maintenance categories fetched dynamically from the database.
  - Specification of exact physical location and urgency priority (`LOW`, `MEDIUM`, `HIGH`, `URGENT`).
  - Optional image attachment with strict server-side validation (allowing only JPEG/PNG, enforcing a 5MB size limit).
  - Anti-tampering protection preventing students from altering status, priority, or assignee via forged POST requests.
- **Implementation Mapping**:
  - Models: [`complaints/models.py:Complaint`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/complaints/models.py)
  - Forms: [`complaints/forms.py:ComplaintCreateForm`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/complaints/forms.py)
  - Views: [`complaints/views.py:create_complaint_view`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/complaints/views.py)
  - Verification: [`complaints/tests.py:StudentViewsAndScopingTests`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/complaints/tests.py), [`dashboard/tests.py:SecurityAndValidationTests`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/dashboard/tests.py)

---

### [FR3] Complaint Triage & Staff Assignment (Admin Portal)
- **Description**: Centralized administrative portal for triaging incoming complaints, allocating technicians, and managing system masters.
- **Key Capabilities**:
  - Real-time KPI summary cards (Total Complaints, Pending Triage, In Progress, Resolved, Closed).
  - Triage modal enabling assignment of `SUBMITTED` complaints to active maintenance staff members.
  - Re-assignment of active tickets with automatic audit logging.
  - Multi-criteria filtering by category, status, priority, technician, submitter, and date ranges.
  - Full CRUD management for maintenance categories.
  - User management interface allowing administrative activation and deactivation of user accounts.
- **Implementation Mapping**:
  - Views: [`dashboard/views.py:admin_dashboard_view`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/dashboard/views.py), [`admin_assign_view`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/dashboard/views.py), [`admin_category_manage_view`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/dashboard/views.py), [`admin_user_manage_view`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/dashboard/views.py)
  - Verification: [`dashboard/tests.py:AdminModuleTests`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/dashboard/tests.py) (8 unit tests)

---

### [FR4] Maintenance Lifecycle & Resolution (Staff Module)
- **Description**: Dedicated portal for maintenance staff to manage assigned work orders through the resolution lifecycle.
- **Key Capabilities**:
  - Personalized work queue displaying only tickets where `assigned_to == request.user`.
  - State transition from `ASSIGNED` &rarr; `IN_PROGRESS` when technician commences repair work.
  - State transition from `IN_PROGRESS` &rarr; `RESOLVED` requiring detailed technical resolution remarks and capturing `resolved_at` timestamp.
  - Archive tab displaying historical complaints previously resolved by the logged-in staff member.
  - Strict IDOR defense returning 404/403 if a technician attempts to access or modify tickets assigned to others.
- **Implementation Mapping**:
  - Views: [`dashboard/views.py:staff_dashboard_view`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/dashboard/views.py), [`staff_start_work_view`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/dashboard/views.py), [`staff_resolve_view`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/dashboard/views.py)
  - State Logic: [`complaints/models.py:Complaint.transition_to`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/complaints/models.py)
  - Verification: [`dashboard/tests.py:StaffModuleTests`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/dashboard/tests.py) (6 unit tests)

---

### [FR5] Resolution Verification & Ticket Closure
- **Description**: Enables students to verify physical repairs and officially close their complaints, with administrative backup closure capability.
- **Key Capabilities**:
  - Complete chronological timeline view of all status changes, timestamps, and actor remarks on the complaint detail page.
  - One-click closure action available to the student submitter once a complaint is in `RESOLVED` status.
  - Automatic capture of `closed_at` timestamp and closure remark logging.
  - Administrative force-close capability for long-standing resolved tickets.
- **Implementation Mapping**:
  - Views: [`complaints/views.py:complaint_detail_view`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/complaints/views.py), [`close_complaint_view`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/complaints/views.py), [`dashboard/views.py:admin_force_close_view`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/dashboard/views.py)
  - Verification: [`complaints/tests.py:ComplaintModelAndStateMachineTests`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/complaints/tests.py)

---

### [FR6] Analytics Dashboard & Data Visualizations
- **Description**: Real-time interactive charts providing administrative visibility into breakdown trends, department workload, and urgency distribution.
- **Key Capabilities**:
  - **Complaints by Category**: Bar chart showing breakdown frequency across campus departments.
  - **Status Breakdown**: Doughnut chart illustrating live progress across the 5 lifecycle states.
  - **Priority Distribution**: Horizontal bar chart highlighting urgent and high-priority maintenance requests.
  - Real database computation using Django ORM aggregation (`annotate(count=Count('id'))`) passed as JSON payloads to Chart.js.
- **Implementation Mapping**:
  - Backend: [`dashboard/views.py:admin_dashboard_view`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/dashboard/views.py)
  - Frontend: [`templates/dashboard/admin_dashboard.html`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/templates/dashboard/admin_dashboard.html), [`static/js/admin_charts.js`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/static/js/admin_charts.js)
  - Verification: [`dashboard/tests.py:AnalyticsDashboardTests`](file:///c:/Users/Sonal/OneDrive/Desktop/Software%20Engineering/dashboard/tests.py) (2 unit tests)

---

## 2. Non-Functional Requirements (NFR) Matrix

| NFR Category | Requirement Specification | Implementation Mechanism | Verification Method |
| :--- | :--- | :--- | :--- |
| **NFR1: Security** | Prevent unauthorized access, privilege escalation, IDOR, and CSRF attacks. | Centralized `@role_required` decorators, server-side queryset filtering (`filter(submitted_by=user)` / `filter(assigned_to=user)`), mandatory Django CSRF middleware, PBKDF2 password hashing, file mime-type verification. | Automated IDOR penetration tests in `dashboard.tests.SecurityAndValidationTests` + mutation tests. |
| **NFR2: Usability & UI** | Intuitive, responsive web design with clear feedback and zero confusing error tracebacks. | Glassmorphism UI tokens, custom responsive layout, flash notification badges, human-friendly 403, 404, and 500 error templates. | Manual UX walk-through across mobile/desktop viewports; custom error handler unit tests. |
| **NFR3: Performance** | Sub-second response times for dashboard loads and search queries. | `select_related()` query optimizations avoiding N+1 queries, database-level aggregation for analytics, indexed foreign keys. | Shell query profiling and automated test execution timing (<0.05s per endpoint). |
| **NFR4: Reliability** | ACID transactional integrity; prevent invalid states or data corruption. | Database-level atomic transactions (`@transaction.atomic`), immutable `ComplaintHistory` audit records, strict state machine validator. | `ComplaintModelAndStateMachineTests` verifying all legal and illegal transitions. |
| **NFR5: Maintainability** | Clean modular architecture adhering to SOLID principles and comprehensive testability. | Separation into `accounts`, `complaints`, and `dashboard` apps, service-layer state machine methods, idempotent demo seeding command. | 47 passing unit and integration tests across all modules. |
