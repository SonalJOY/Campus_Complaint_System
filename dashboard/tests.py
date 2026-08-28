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
