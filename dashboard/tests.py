from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from accounts.models import Profile
from complaints.models import Category, Complaint, ComplaintHistory


class AdminModuleTests(TestCase):
    def setUp(self):
        self.client = Client()

        # 1. Create Admin User
        self.admin = User.objects.create_user(
            username='admin_boss',
            email='admin@campus.edu',
            password='password123',
            first_name='Clara',
            last_name='Admin'
        )
        self.admin.profile.role = Profile.ROLE_ADMIN
        self.admin.profile.phone = '+1-555-0303'
        self.admin.profile.save()

        # 2. Create Staff Users
        self.staff1 = User.objects.create_user(
            username='staff_john',
            email='john@campus.edu',
            password='password123',
            first_name='John',
            last_name='Electrician'
        )
        self.staff1.profile.role = Profile.ROLE_STAFF
        self.staff1.profile.phone = '+1-555-0111'
        self.staff1.profile.save()

        self.staff2 = User.objects.create_user(
            username='staff_mike',
            email='mike@campus.edu',
            password='password123',
            first_name='Mike',
            last_name='Plumber'
        )
        self.staff2.profile.role = Profile.ROLE_STAFF
        self.staff2.profile.phone = '+1-555-0222'
        self.staff2.profile.save()

        # 3. Create Student Users
        self.student = User.objects.create_user(
            username='student_alice',
            email='alice@campus.edu',
            password='password123',
            first_name='Alice',
            last_name='Smith'
        )
        self.student.profile.role = Profile.ROLE_STUDENT
        self.student.profile.phone = '+1-555-0444'
        self.student.profile.save()

        # 4. Categories
        self.cat_elec = Category.objects.create(name='Electrical', description='Wiring and lights')
        self.cat_plumb = Category.objects.create(name='Plumbing', description='Water and pipes')

        # 5. Complaints in various states
        self.c_submitted = Complaint.objects.create(
            title="Sparking outlet in Lab 1",
            description="Sparking and smell of burning wire",
            category=self.cat_elec,
            location="Block A, Lab 1",
            priority=Complaint.PRIORITY_URGENT,
            status=Complaint.STATUS_SUBMITTED,
            submitted_by=self.student
        )

        self.c_assigned = Complaint.objects.create(
            title="Dripping faucet in 2nd floor restroom",
            description="Continuous leak from tap",
            category=self.cat_plumb,
            location="Block B, Restroom 202",
            priority=Complaint.PRIORITY_LOW,
            status=Complaint.STATUS_ASSIGNED,
            submitted_by=self.student,
            assigned_to=self.staff2
        )

        self.c_inprogress = Complaint.objects.create(
            title="Main AC cooling coil repair",
            description="Technician servicing compressor",
            category=self.cat_elec,
            location="Auditorium",
            priority=Complaint.PRIORITY_HIGH,
            status=Complaint.STATUS_IN_PROGRESS,
            submitted_by=self.student,
            assigned_to=self.staff1
        )

        self.c_resolved = Complaint.objects.create(
            title="Broken chair fixed",
            description="Welded chair frame",
            category=self.cat_plumb,
            location="Room 101",
            priority=Complaint.PRIORITY_MEDIUM,
            status=Complaint.STATUS_RESOLVED,
            submitted_by=self.student,
            assigned_to=self.staff2
        )

        self.c_closed = Complaint.objects.create(
            title="Replaced projector bulb",
            description="New lamp installed",
            category=self.cat_elec,
            location="Room 303",
            priority=Complaint.PRIORITY_MEDIUM,
            status=Complaint.STATUS_CLOSED,
            submitted_by=self.student,
            assigned_to=self.staff1
        )

    # --------------------------------------------------------------------------
    # RBAC SECURITY TESTS
    # --------------------------------------------------------------------------

    def test_admin_portal_rbac_authorization(self):
        """
        Verify that only users with the ADMIN role can access admin views,
        while Students and Staff receive HTTP 403 Forbidden.
        """
        admin_urls = [
            reverse('dashboard:admin_dashboard'),
            reverse('dashboard:admin_complaint_list'),
            reverse('dashboard:admin_complaint_detail', kwargs={'complaint_id': self.c_submitted.complaint_id}),
            reverse('dashboard:admin_category_list'),
            reverse('dashboard:admin_category_create'),
            reverse('dashboard:admin_user_list'),
        ]

        # 1. Anonymous user redirected to login
        for url in admin_urls:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 302, f"Anon user was not redirected for {url}")
            self.assertIn(reverse('accounts:login'), res.url)

        # 2. Student user gets 403
        self.client.login(username='student_alice', password='password123')
        for url in admin_urls:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 403, f"Student was not forbidden for {url}")

        # 3. Staff user gets 403
        self.client.login(username='staff_john', password='password123')
        for url in admin_urls:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 403, f"Staff was not forbidden for {url}")

        # 4. Admin user gets 200 OK
        self.client.login(username='admin_boss', password='password123')
        for url in admin_urls:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200, f"Admin could not access {url}")

    # --------------------------------------------------------------------------
    # ADMIN DASHBOARD STATS & QUEUE
    # --------------------------------------------------------------------------

    def test_admin_dashboard_statistics_and_queues(self):
        self.client.login(username='admin_boss', password='password123')
        response = self.client.get(reverse('dashboard:admin_dashboard'))
        self.assertEqual(response.status_code, 200)

        # Counters
        self.assertEqual(response.context['total_count'], 5)
        self.assertEqual(response.context['submitted_count'], 1)
        self.assertEqual(response.context['in_progress_count'], 1)
        self.assertEqual(response.context['resolved_count'], 1)
        self.assertEqual(response.context['closed_count'], 1)
        # High priority active count (c_submitted is URGENT, c_inprogress is HIGH) -> 2
        self.assertEqual(response.context['high_priority_count'], 2)

        # Queues
        self.assertEqual(len(response.context['unassigned_complaints']), 1)
        self.assertEqual(response.context['unassigned_complaints'][0].complaint_id, self.c_submitted.complaint_id)

    # --------------------------------------------------------------------------
    # COMPLAINT LIST SEARCH & FILTERS
    # --------------------------------------------------------------------------

    def test_admin_complaint_list_filters(self):
        self.client.login(username='admin_boss', password='password123')
        list_url = reverse('dashboard:admin_complaint_list')

        # 1. Base list: All 5 complaints
        res = self.client.get(list_url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['page_obj'].paginator.count, 5)

        # 2. Search query by keyword
        res = self.client.get(list_url, {'q': 'Sparking'})
        self.assertEqual(res.context['page_obj'].paginator.count, 1)
        self.assertEqual(res.context['complaints'][0].complaint_id, self.c_submitted.complaint_id)

        # 3. Filter by Status
        res = self.client.get(list_url, {'status': 'IN_PROGRESS'})
        self.assertEqual(res.context['page_obj'].paginator.count, 1)
        self.assertEqual(res.context['complaints'][0].complaint_id, self.c_inprogress.complaint_id)

        # 4. Filter by Priority
        res = self.client.get(list_url, {'priority': 'URGENT'})
        self.assertEqual(res.context['page_obj'].paginator.count, 1)
        self.assertEqual(res.context['complaints'][0].complaint_id, self.c_submitted.complaint_id)

        # 5. Filter by Assigned Staff
        res = self.client.get(list_url, {'assigned_to': self.staff1.id})
        self.assertEqual(res.context['page_obj'].paginator.count, 2)

        # 6. Filter Unassigned Only
        res = self.client.get(list_url, {'assigned_to': 'unassigned'})
        self.assertEqual(res.context['page_obj'].paginator.count, 1)
        self.assertEqual(res.context['complaints'][0].complaint_id, self.c_submitted.complaint_id)

    # --------------------------------------------------------------------------
    # ASSIGNMENT, REASSIGNMENT & TRANSITION FLOWS
    # --------------------------------------------------------------------------

    def test_admin_assigns_submitted_complaint_end_to_end(self):
        """
        Verify SUBMITTED -> ASSIGNED state machine transition when admin assigns a staff member.
        """
        self.client.login(username='admin_boss', password='password123')
        detail_url = reverse('dashboard:admin_complaint_detail', kwargs={'complaint_id': self.c_submitted.complaint_id})

        payload = {
            'assigned_to': self.staff1.id,
            'priority': Complaint.PRIORITY_URGENT,
            'remarks': 'Assigned to senior electrician. Please inspect immediately.'
        }

        response = self.client.post(detail_url, data=payload, follow=True)
        self.assertEqual(response.status_code, 200)

        # Verify DB state
        self.c_submitted.refresh_from_db()
        self.assertEqual(self.c_submitted.status, Complaint.STATUS_ASSIGNED)
        self.assertEqual(self.c_submitted.assigned_to, self.staff1)

        # Verify Audit History
        last_history = self.c_submitted.history.first()
        self.assertIsNotNone(last_history)
        self.assertEqual(last_history.old_status, Complaint.STATUS_SUBMITTED)
        self.assertEqual(last_history.new_status, Complaint.STATUS_ASSIGNED)
        self.assertEqual(last_history.changed_by, self.admin)
        self.assertIn('Assigned to senior electrician', last_history.remarks)

    def test_admin_reassigns_assigned_complaint(self):
        """
        Verify admin reassigning an already ASSIGNED complaint updates assigned_to and logs an audit trail.
        """
        self.client.login(username='admin_boss', password='password123')
        detail_url = reverse('dashboard:admin_complaint_detail', kwargs={'complaint_id': self.c_assigned.complaint_id})

        # Reassign from staff2 to staff1
        payload = {
            'assigned_to': self.staff1.id,
            'priority': Complaint.PRIORITY_MEDIUM,
            'remarks': 'Reassigning to John due to technician availability.'
        }

        response = self.client.post(detail_url, data=payload, follow=True)
        self.assertEqual(response.status_code, 200)

        self.c_assigned.refresh_from_db()
        self.assertEqual(self.c_assigned.assigned_to, self.staff1)
        self.assertEqual(self.c_assigned.priority, Complaint.PRIORITY_MEDIUM)

        # Audit History Check
        last_history = self.c_assigned.history.first()
        self.assertEqual(last_history.old_status, Complaint.STATUS_ASSIGNED)
        self.assertEqual(last_history.new_status, Complaint.STATUS_ASSIGNED)
        self.assertEqual(last_history.changed_by, self.admin)
        self.assertIn('Reassigned from', last_history.remarks)

    def test_admin_force_close_resolved_complaint(self):
        """
        Verify admin can officially close a RESOLVED complaint (RESOLVED -> CLOSED).
        """
        self.client.login(username='admin_boss', password='password123')
        close_url = reverse('dashboard:admin_complaint_force_close', kwargs={'complaint_id': self.c_resolved.complaint_id})

        response = self.client.post(close_url, data={'remarks': 'Admin verified resolution with supervisor.'}, follow=True)
        self.assertEqual(response.status_code, 200)

        self.c_resolved.refresh_from_db()
        self.assertEqual(self.c_resolved.status, Complaint.STATUS_CLOSED)
        self.assertIsNotNone(self.c_resolved.closed_at)

        last_history = self.c_resolved.history.first()
        self.assertEqual(last_history.old_status, Complaint.STATUS_RESOLVED)
        self.assertEqual(last_history.new_status, Complaint.STATUS_CLOSED)
        self.assertEqual(last_history.changed_by, self.admin)

    # --------------------------------------------------------------------------
    # CATEGORY CRUD TESTS
    # --------------------------------------------------------------------------

    def test_category_management_crud(self):
        self.client.login(username='admin_boss', password='password123')

        # 1. Create Category
        create_url = reverse('dashboard:admin_category_create')
        res = self.client.post(create_url, {
            'name': 'HVAC / Ventilation',
            'description': 'Air filters, cooling towers, duct cleaning',
            'is_active': True
        }, follow=True)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(Category.objects.filter(name='HVAC / Ventilation').exists())
        hvac_cat = Category.objects.get(name='HVAC / Ventilation')

        # 2. Edit Category
        edit_url = reverse('dashboard:admin_category_edit', kwargs={'pk': hvac_cat.pk})
        res = self.client.post(edit_url, {
            'name': 'HVAC & Air Systems',
            'description': 'Updated scope description',
            'is_active': True
        }, follow=True)
        self.assertEqual(res.status_code, 200)
        hvac_cat.refresh_from_db()
        self.assertEqual(hvac_cat.name, 'HVAC & Air Systems')

        # 3. Toggle Active Status
        toggle_url = reverse('dashboard:admin_category_toggle', kwargs={'pk': hvac_cat.pk})
        res = self.client.post(toggle_url, follow=True)
        self.assertEqual(res.status_code, 200)
        hvac_cat.refresh_from_db()
        self.assertFalse(hvac_cat.is_active)

    # --------------------------------------------------------------------------
    # USER DIRECTORY & STATUS TOGGLE TESTS
    # --------------------------------------------------------------------------

    def test_user_management_and_toggle(self):
        self.client.login(username='admin_boss', password='password123')

        # 1. List view & role filter
        user_list_url = reverse('dashboard:admin_user_list')
        res = self.client.get(user_list_url, {'role': 'STUDENT'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['page_obj'].paginator.count, 1)

        # 2. Deactivate student account
        toggle_url = reverse('dashboard:admin_user_toggle_status', kwargs={'user_id': self.student.id})
        res = self.client.post(toggle_url, follow=True)
        self.assertEqual(res.status_code, 200)
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_active)

        # 3. Re-activate student account
        res = self.client.post(toggle_url, follow=True)
        self.assertEqual(res.status_code, 200)
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_active)

        # 4. Self-deactivation blocked
        self_toggle = reverse('dashboard:admin_user_toggle_status', kwargs={'user_id': self.admin.id})
        res = self.client.post(self_toggle, follow=True)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)


class StaffModuleTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Create Staff 1
        self.staff1 = User.objects.create_user(
            username='staff_john',
            email='john@campus.edu',
            password='password123',
            first_name='John',
            last_name='Electrician'
        )
        self.staff1.profile.role = Profile.ROLE_STAFF
        self.staff1.profile.phone = '+1-555-0111'
        self.staff1.profile.save()

        # Create Staff 2
        self.staff2 = User.objects.create_user(
            username='staff_mike',
            email='mike@campus.edu',
            password='password123',
            first_name='Mike',
            last_name='Plumber'
        )
        self.staff2.profile.role = Profile.ROLE_STAFF
        self.staff2.profile.phone = '+1-555-0222'
        self.staff2.profile.save()

        # Create Student
        self.student = User.objects.create_user(
            username='student_alice',
            email='alice@campus.edu',
            password='password123',
            first_name='Alice',
            last_name='Smith'
        )
        self.student.profile.role = Profile.ROLE_STUDENT
        self.student.profile.save()

        # Category
        self.category = Category.objects.create(name='Electrical', description='Wiring and lights')

        # Complaints for Staff 1
        self.c_assigned = Complaint.objects.create(
            title="Broken switch in Room 201",
            description="Switch sparking",
            category=self.category,
            location="Room 201",
            priority=Complaint.PRIORITY_HIGH,
            status=Complaint.STATUS_ASSIGNED,
            submitted_by=self.student,
            assigned_to=self.staff1
        )

        self.c_inprogress = Complaint.objects.create(
            title="AC repair in Hall B",
            description="Testing capacitor",
            category=self.category,
            location="Hall B",
            priority=Complaint.PRIORITY_URGENT,
            status=Complaint.STATUS_IN_PROGRESS,
            submitted_by=self.student,
            assigned_to=self.staff1
        )

        self.c_resolved = Complaint.objects.create(
            title="Fluorescent bulb changed",
            description="New tube installed",
            category=self.category,
            location="Room 102",
            priority=Complaint.PRIORITY_LOW,
            status=Complaint.STATUS_RESOLVED,
            submitted_by=self.student,
            assigned_to=self.staff1
        )

        # Complaint for Staff 2 (to test strict scoping)
        self.c_staff2 = Complaint.objects.create(
            title="Mike's private plumbing task",
            description="Pipe leak",
            category=self.category,
            location="Washroom 4",
            priority=Complaint.PRIORITY_MEDIUM,
            status=Complaint.STATUS_ASSIGNED,
            submitted_by=self.student,
            assigned_to=self.staff2
        )

    def test_staff_dashboard_metrics_and_scoping(self):
        self.client.login(username='staff_john', password='password123')
        response = self.client.get(reverse('dashboard:staff_dashboard'))
        self.assertEqual(response.status_code, 200)

        # Counters should only count complaints assigned to staff1 (total 3)
        self.assertEqual(response.context['total_assigned_count'], 3)
        self.assertEqual(response.context['pending_assigned_count'], 1)
        self.assertEqual(response.context['in_progress_count'], 1)
        self.assertEqual(response.context['resolved_count'], 1)
        self.assertEqual(response.context['high_priority_count'], 2)

        # Active tasks queue contains c_inprogress and c_assigned, but NOT c_staff2
        active_ids = [t.complaint_id for t in response.context['active_tasks']]
        self.assertIn(self.c_assigned.complaint_id, active_ids)
        self.assertIn(self.c_inprogress.complaint_id, active_ids)
        self.assertNotIn(self.c_staff2.complaint_id, active_ids)

    def test_staff_complaint_list_and_tabs(self):
        self.client.login(username='staff_john', password='password123')
        list_url = reverse('dashboard:staff_complaint_list')

        # 1. Active tab (default): ASSIGNED + IN_PROGRESS (2 items)
        res_active = self.client.get(list_url, {'tab': 'active'})
        self.assertEqual(res_active.status_code, 200)
        self.assertEqual(res_active.context['page_obj'].paginator.count, 2)

        # 2. Resolved tab: RESOLVED (1 item)
        res_resolved = self.client.get(list_url, {'tab': 'resolved'})
        self.assertEqual(res_resolved.context['page_obj'].paginator.count, 1)
        self.assertEqual(res_resolved.context['complaints'][0].complaint_id, self.c_resolved.complaint_id)

        # 3. Search query
        res_search = self.client.get(list_url, {'tab': 'all', 'q': 'switch'})
        self.assertEqual(res_search.context['page_obj'].paginator.count, 1)
        self.assertEqual(res_search.context['complaints'][0].complaint_id, self.c_assigned.complaint_id)

    def test_strict_staff_authorization_and_scoping(self):
        """
        Verify that Staff 1 cannot view or modify Staff 2's assigned complaint (404 returned).
        """
        self.client.login(username='staff_john', password='password123')

        # Attempt to view Staff 2's complaint detail
        detail_url = reverse('dashboard:staff_complaint_detail', kwargs={'complaint_id': self.c_staff2.complaint_id})
        res_detail = self.client.get(detail_url)
        self.assertEqual(res_detail.status_code, 404)

        # Attempt to start work on Staff 2's complaint
        start_url = reverse('dashboard:staff_complaint_start_work', kwargs={'complaint_id': self.c_staff2.complaint_id})
        res_start = self.client.post(start_url)
        self.assertEqual(res_start.status_code, 404)

        # Attempt to resolve Staff 2's complaint
        resolve_url = reverse('dashboard:staff_complaint_resolve', kwargs={'complaint_id': self.c_staff2.complaint_id})
        res_resolve = self.client.post(resolve_url, {'remarks': 'Hacked resolution'})
        self.assertEqual(res_resolve.status_code, 404)

    def test_staff_start_work_transition(self):
        """
        Verify ASSIGNED -> IN_PROGRESS transition by assigned technician.
        """
        self.client.login(username='staff_john', password='password123')
        start_url = reverse('dashboard:staff_complaint_start_work', kwargs={'complaint_id': self.c_assigned.complaint_id})

        res = self.client.post(start_url, {'remarks': 'Technician arrived on site and started repairs.'}, follow=True)
        self.assertEqual(res.status_code, 200)

        self.c_assigned.refresh_from_db()
        self.assertEqual(self.c_assigned.status, Complaint.STATUS_IN_PROGRESS)

        # History entry check
        h = self.c_assigned.history.first()
        self.assertEqual(h.old_status, Complaint.STATUS_ASSIGNED)
        self.assertEqual(h.new_status, Complaint.STATUS_IN_PROGRESS)
        self.assertEqual(h.changed_by, self.staff1)

    def test_staff_resolve_transition_and_mandatory_remarks(self):
        """
        Verify IN_PROGRESS -> RESOLVED transition requires remarks and updates resolved_at.
        """
        self.client.login(username='staff_john', password='password123')
        resolve_url = reverse('dashboard:staff_complaint_resolve', kwargs={'complaint_id': self.c_inprogress.complaint_id})

        # 1. Empty remarks should fail
        res_empty = self.client.post(resolve_url, {'remarks': '   '}, follow=True)
        self.c_inprogress.refresh_from_db()
        self.assertEqual(self.c_inprogress.status, Complaint.STATUS_IN_PROGRESS)

        # 2. Valid remarks should succeed
        res_valid = self.client.post(resolve_url, {
            'remarks': 'Replaced 40uF capacitor, cleaned dust from coils, and verified cooling at 18C.'
        }, follow=True)
        self.assertEqual(res_valid.status_code, 200)

        self.c_inprogress.refresh_from_db()
        self.assertEqual(self.c_inprogress.status, Complaint.STATUS_RESOLVED)
        self.assertIsNotNone(self.c_inprogress.resolved_at)

        # History entry check
        h = self.c_inprogress.history.first()
        self.assertEqual(h.old_status, Complaint.STATUS_IN_PROGRESS)
        self.assertEqual(h.new_status, Complaint.STATUS_RESOLVED)
        self.assertEqual(h.changed_by, self.staff1)
        self.assertIn('Replaced 40uF capacitor', h.remarks)

    def test_student_blocked_from_staff_urls(self):
        """
        Verify student user receives HTTP 403 Forbidden on staff URLs.
        """
        self.client.login(username='student_alice', password='password123')
        staff_urls = [
            reverse('dashboard:staff_dashboard'),
            reverse('dashboard:staff_complaint_list'),
            reverse('dashboard:staff_complaint_detail', kwargs={'complaint_id': self.c_assigned.complaint_id}),
        ]
        for u in staff_urls:
            res = self.client.get(u)
            self.assertEqual(res.status_code, 403)


class AnalyticsDashboardTests(TestCase):
    def setUp(self):
        self.client = Client()
        import json
        self.json = json

        # Users
        self.admin = User.objects.create_user(username='admin_analytics', password='password123', email='admin@test.com')
        self.admin.profile.role = Profile.ROLE_ADMIN
        self.admin.profile.save()

        self.student = User.objects.create_user(username='student_analytics', password='password123', email='student@test.com')
        self.student.profile.role = Profile.ROLE_STUDENT
        self.student.profile.save()

        self.staff = User.objects.create_user(username='staff_analytics', password='password123', email='staff@test.com')
        self.staff.profile.role = Profile.ROLE_STAFF
        self.staff.profile.save()

        # Categories
        self.cat_elec = Category.objects.create(name='Electrical')
        self.cat_plumb = Category.objects.create(name='Plumbing')
        self.cat_it = Category.objects.create(name='IT Hardware')

        # Create Complaints with varied status & priority
        # 1. Electrical / SUBMITTED / HIGH
        Complaint.objects.create(
            title="Broken switch", description="desc", category=self.cat_elec,
            location="Room 1", priority=Complaint.PRIORITY_HIGH,
            status=Complaint.STATUS_SUBMITTED, submitted_by=self.student
        )
        # 2. Electrical / ASSIGNED / URGENT
        Complaint.objects.create(
            title="Short circuit", description="desc", category=self.cat_elec,
            location="Room 2", priority=Complaint.PRIORITY_URGENT,
            status=Complaint.STATUS_ASSIGNED, submitted_by=self.student, assigned_to=self.staff
        )
        # 3. Plumbing / IN_PROGRESS / MEDIUM
        Complaint.objects.create(
            title="Leak pipe", description="desc", category=self.cat_plumb,
            location="Room 3", priority=Complaint.PRIORITY_MEDIUM,
            status=Complaint.STATUS_IN_PROGRESS, submitted_by=self.student, assigned_to=self.staff
        )
        # 4. IT Hardware / RESOLVED / LOW
        Complaint.objects.create(
            title="Mouse broken", description="desc", category=self.cat_it,
            location="Lab 1", priority=Complaint.PRIORITY_LOW,
            status=Complaint.STATUS_RESOLVED, submitted_by=self.student, assigned_to=self.staff
        )

    def test_admin_dashboard_chart_json_payloads(self):
        """
        Verify Chart.js JSON payloads match real database counts accurately.
        """
        self.client.login(username='admin_analytics', password='password123')
        res = self.client.get(reverse('dashboard:admin_dashboard'))
        self.assertEqual(res.status_code, 200)

        # 1. Verify JSON exists in context
        self.assertIn('category_chart_json', res.context)
        self.assertIn('status_chart_json', res.context)
        self.assertIn('priority_chart_json', res.context)

        # 2. Parse Category Chart Data
        cat_data = self.json.loads(res.context['category_chart_json'])
        cat_map = dict(zip(cat_data['labels'], cat_data['data']))
        self.assertEqual(cat_map.get('Electrical'), 2)
        self.assertEqual(cat_map.get('Plumbing'), 1)
        self.assertEqual(cat_map.get('IT Hardware'), 1)

        # 3. Parse Status Chart Data
        status_data = self.json.loads(res.context['status_chart_json'])
        status_map = dict(zip(status_data['labels'], status_data['data']))
        self.assertEqual(status_map.get('Submitted'), 1)
        self.assertEqual(status_map.get('Assigned'), 1)
        self.assertEqual(status_map.get('In Progress'), 1)
        self.assertEqual(status_map.get('Resolved'), 1)
        self.assertEqual(status_map.get('Closed'), 0)

        # 4. Parse Priority Chart Data
        priority_data = self.json.loads(res.context['priority_chart_json'])
        priority_map = dict(zip(priority_data['labels'], priority_data['data']))
        self.assertEqual(priority_map.get('Low'), 1)
        self.assertEqual(priority_map.get('Medium'), 1)
        self.assertEqual(priority_map.get('High'), 1)
        self.assertEqual(priority_map.get('Urgent'), 1)

    def test_dynamic_chart_update_on_data_change(self):
        """
        Confirm charts update dynamically when new records are added or state changes.
        """
        self.client.login(username='admin_analytics', password='password123')

        # Add a new Plumbing / URGENT complaint
        Complaint.objects.create(
            title="Burst main pipe", description="Flooding", category=self.cat_plumb,
            location="Basement", priority=Complaint.PRIORITY_URGENT,
            status=Complaint.STATUS_SUBMITTED, submitted_by=self.student
        )

        res = self.client.get(reverse('dashboard:admin_dashboard'))
        cat_data = self.json.loads(res.context['category_chart_json'])
        cat_map = dict(zip(cat_data['labels'], cat_data['data']))
        self.assertEqual(cat_map.get('Plumbing'), 2)  # incremented from 1 to 2

        status_data = self.json.loads(res.context['status_chart_json'])
        status_map = dict(zip(status_data['labels'], status_data['data']))
        self.assertEqual(status_map.get('Submitted'), 2)  # incremented from 1 to 2

        priority_data = self.json.loads(res.context['priority_chart_json'])
        priority_map = dict(zip(priority_data['labels'], priority_data['data']))
        self.assertEqual(priority_map.get('Urgent'), 2)  # incremented from 1 to 2


class SecurityAndValidationTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Student 1
        self.student1 = User.objects.create_user(username='student_sec1', email='s1@test.com', password='password123')
        self.student1.profile.role = Profile.ROLE_STUDENT
        self.student1.profile.save()

        # Student 2
        self.student2 = User.objects.create_user(username='student_sec2', email='s2@test.com', password='password123')
        self.student2.profile.role = Profile.ROLE_STUDENT
        self.student2.profile.save()

        # Staff 1
        self.staff1 = User.objects.create_user(username='staff_sec1', email='st1@test.com', password='password123')
        self.staff1.profile.role = Profile.ROLE_STAFF
        self.staff1.profile.save()

        # Staff 2
        self.staff2 = User.objects.create_user(username='staff_sec2', email='st2@test.com', password='password123')
        self.staff2.profile.role = Profile.ROLE_STAFF
        self.staff2.profile.save()

        # Category
        self.category = Category.objects.create(name='Security Test Category')

        # Student 1 Complaint
        self.c1 = Complaint.objects.create(
            title="Student 1 Ticket",
            description="desc",
            category=self.category,
            location="Location 1",
            status=Complaint.STATUS_ASSIGNED,
            submitted_by=self.student1,
            assigned_to=self.staff1
        )

        # Student 2 Complaint (Resolved)
        self.c2_resolved = Complaint.objects.create(
            title="Student 2 Resolved Ticket",
            description="desc",
            category=self.category,
            location="Location 2",
            status=Complaint.STATUS_RESOLVED,
            submitted_by=self.student2,
            assigned_to=self.staff2
        )

    def test_student_cannot_tamper_administrative_fields_on_create(self):
        """
        Verify that submitting forged POST parameters (status=CLOSED, assigned_to=1)
        are ignored and the ticket is strictly created as SUBMITTED with assigned_to=None.
        """
        self.client.login(username='student_sec1', password='password123')
        url = reverse('complaints:student_complaint_create')

        forged_payload = {
            'title': 'Hacked Ticket',
            'description': 'Attempting status escalation',
            'category': self.category.id,
            'location': 'Lab 1',
            'priority': Complaint.PRIORITY_HIGH,
            # Forged fields:
            'status': Complaint.STATUS_CLOSED,
            'assigned_to': self.staff1.id,
            'submitted_by': self.student2.id,
        }

        res = self.client.post(url, forged_payload, follow=True)
        self.assertEqual(res.status_code, 200)

        created_ticket = Complaint.objects.get(title='Hacked Ticket')
        self.assertEqual(created_ticket.status, Complaint.STATUS_SUBMITTED)  # NOT CLOSED
        self.assertIsNone(created_ticket.assigned_to)  # NOT STAFF1
        self.assertEqual(created_ticket.submitted_by, self.student1)  # NOT STUDENT2

    def test_student_idor_defense(self):
        """
        Verify Student 1 cannot view or close Student 2's complaint (returns 404).
        """
        self.client.login(username='student_sec1', password='password123')

        # Attempt to view Student 2's complaint
        res_view = self.client.get(reverse('complaints:student_complaint_detail', kwargs={'complaint_id': self.c2_resolved.complaint_id}))
        self.assertEqual(res_view.status_code, 404)

        # Attempt to close Student 2's complaint
        res_close = self.client.post(reverse('complaints:student_complaint_close', kwargs={'complaint_id': self.c2_resolved.complaint_id}), {'remarks': 'Hacked close'})
        self.assertEqual(res_close.status_code, 404)

    def test_staff_idor_defense(self):
        """
        Verify Staff 1 cannot view, start work, or resolve Staff 2's complaint (returns 404).
        """
        self.client.login(username='staff_sec1', password='password123')

        res_view = self.client.get(reverse('dashboard:staff_complaint_detail', kwargs={'complaint_id': self.c2_resolved.complaint_id}))
        self.assertEqual(res_view.status_code, 404)

        res_start = self.client.post(reverse('dashboard:staff_complaint_start_work', kwargs={'complaint_id': self.c2_resolved.complaint_id}))
        self.assertEqual(res_start.status_code, 404)

        res_resolve = self.client.post(reverse('dashboard:staff_complaint_resolve', kwargs={'complaint_id': self.c2_resolved.complaint_id}), {'remarks': 'Hacked'})
        self.assertEqual(res_resolve.status_code, 404)

    def test_custom_error_handlers(self):
        """
        Verify custom 403, 404, and 500 error pages render cleanly.
        """
        from django.test import RequestFactory
        from config.views import custom_403, custom_404, custom_500

        factory = RequestFactory()

        # 403
        req_403 = factory.get('/')
        req_403.user = self.student1
        res_403 = custom_403(req_403)
        self.assertEqual(res_403.status_code, 403)
        self.assertIn(b'Access Restricted', res_403.content)

        # 404
        req_404 = factory.get('/')
        req_404.user = self.student1
        res_404 = custom_404(req_404)
        self.assertEqual(res_404.status_code, 404)
        self.assertIn(b'Resource Not Found', res_404.content)

        # 500
        req_500 = factory.get('/')
        req_500.user = self.student1
        res_500 = custom_500(req_500)
        self.assertEqual(res_500.status_code, 500)
        self.assertIn(b'Server Error', res_500.content)



