import io
from PIL import Image
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from accounts.models import Profile
from .models import Category, Complaint, ComplaintHistory, InvalidStatusTransitionError


class ComplaintModelAndStateMachineTests(TestCase):
    """
    Unit tests for Complaint model, sequential ID generation, and strict lifecycle transitions.
    """
    def setUp(self):
        # Users
        self.student = User.objects.create_user(username='student1', password='pass123')
        self.student.profile.role = Profile.ROLE_STUDENT
        self.student.profile.save()

        self.other_student = User.objects.create_user(username='student2', password='pass123')
        self.other_student.profile.role = Profile.ROLE_STUDENT
        self.other_student.profile.save()

        self.staff1 = User.objects.create_user(username='staff_electrician', password='pass123')
        self.staff1.profile.role = Profile.ROLE_STAFF
        self.staff1.profile.save()

        self.staff2 = User.objects.create_user(username='staff_plumber', password='pass123')
        self.staff2.profile.role = Profile.ROLE_STAFF
        self.staff2.profile.save()

        self.admin = User.objects.create_user(username='campus_admin', password='pass123')
        self.admin.profile.role = Profile.ROLE_ADMIN
        self.admin.profile.save()

        # Category
        self.category_elec = Category.objects.create(
            name='Electrical',
            description='Power outlets, lighting, wiring issues'
        )

    def test_complaint_id_auto_generation_and_initial_status(self):
        """
        Verify complaints get unique sequential IDs (CMP-000001, etc.) and start as SUBMITTED.
        """
        c1 = Complaint.objects.create(
            title="Broken switch in Lab 1",
            description="Switch sparked and is dead",
            category=self.category_elec,
            location="Block A, Lab 1",
            priority=Complaint.PRIORITY_HIGH,
            submitted_by=self.student
        )
        c2 = Complaint.objects.create(
            title="Fluorescent bulb flickering",
            description="Bulb flickering constantly",
            category=self.category_elec,
            location="Block A, Room 102",
            priority=Complaint.PRIORITY_LOW,
            submitted_by=self.student
        )
        self.assertTrue(c1.complaint_id.startswith("CMP-"))
        self.assertTrue(c2.complaint_id.startswith("CMP-"))
        self.assertNotEqual(c1.complaint_id, c2.complaint_id)
        self.assertEqual(c1.status, Complaint.STATUS_SUBMITTED)
        self.assertIsNone(c1.assigned_to)

    def test_full_valid_state_machine_lifecycle(self):
        """
        Test valid chain: SUBMITTED -> ASSIGNED -> IN_PROGRESS -> RESOLVED -> CLOSED
        """
        complaint = Complaint.objects.create(
            title="AC not cooling",
            description="AC fan runs but no cooling in seminar hall",
            category=self.category_elec,
            location="Main Auditorium",
            priority=Complaint.PRIORITY_HIGH,
            submitted_by=self.student
        )

        # 1. SUBMITTED -> ASSIGNED (by Admin)
        complaint.transition_to(
            new_status=Complaint.STATUS_ASSIGNED,
            user=self.admin,
            remarks="Assigned to electrical team lead",
            assigned_to_user=self.staff1
        )
        complaint.refresh_from_db()
        self.assertEqual(complaint.status, Complaint.STATUS_ASSIGNED)
        self.assertEqual(complaint.assigned_to, self.staff1)

        # 2. ASSIGNED -> IN_PROGRESS (by assigned Staff)
        complaint.transition_to(
            new_status=Complaint.STATUS_IN_PROGRESS,
            user=self.staff1,
            remarks="Diagnosing compressor capacitor"
        )
        complaint.refresh_from_db()
        self.assertEqual(complaint.status, Complaint.STATUS_IN_PROGRESS)

        # 3. IN_PROGRESS -> RESOLVED (by assigned Staff, with resolution remark)
        complaint.transition_to(
            new_status=Complaint.STATUS_RESOLVED,
            user=self.staff1,
            remarks="Replaced 45uF capacitor and tested airflow temperature."
        )
        complaint.refresh_from_db()
        self.assertEqual(complaint.status, Complaint.STATUS_RESOLVED)
        self.assertIsNotNone(complaint.resolved_at)

        # 4. RESOLVED -> CLOSED (by Submitting Student)
        complaint.transition_to(
            new_status=Complaint.STATUS_CLOSED,
            user=self.student,
            remarks="Verified room is cold now. Thank you!"
        )
        complaint.refresh_from_db()
        self.assertEqual(complaint.status, Complaint.STATUS_CLOSED)
        self.assertIsNotNone(complaint.closed_at)

        # Verify audit history
        history_records = complaint.history.all().order_by('changed_at')
        self.assertEqual(history_records.count(), 4)
        
        self.assertEqual(history_records[0].old_status, Complaint.STATUS_SUBMITTED)
        self.assertEqual(history_records[0].new_status, Complaint.STATUS_ASSIGNED)
        self.assertEqual(history_records[0].changed_by, self.admin)

        self.assertEqual(history_records[1].old_status, Complaint.STATUS_ASSIGNED)
        self.assertEqual(history_records[1].new_status, Complaint.STATUS_IN_PROGRESS)
        self.assertEqual(history_records[1].changed_by, self.staff1)

        self.assertEqual(history_records[2].old_status, Complaint.STATUS_IN_PROGRESS)
        self.assertEqual(history_records[2].new_status, Complaint.STATUS_RESOLVED)
        self.assertEqual(history_records[2].changed_by, self.staff1)

        self.assertEqual(history_records[3].old_status, Complaint.STATUS_RESOLVED)
        self.assertEqual(history_records[3].new_status, Complaint.STATUS_CLOSED)
        self.assertEqual(history_records[3].changed_by, self.student)

    def test_admin_can_close_resolved_complaint(self):
        """
        Verify administrators can also close a resolved complaint.
        """
        complaint = Complaint.objects.create(
            title="Broken socket", description="Loose wire", category=self.category_elec,
            location="Room 10", priority=Complaint.PRIORITY_MEDIUM, submitted_by=self.student
        )
        complaint.transition_to(Complaint.STATUS_ASSIGNED, user=self.admin, assigned_to_user=self.staff1)
        complaint.transition_to(Complaint.STATUS_IN_PROGRESS, user=self.staff1)
        complaint.transition_to(Complaint.STATUS_RESOLVED, user=self.staff1, remarks="Replaced socket unit")
        
        complaint.transition_to(Complaint.STATUS_CLOSED, user=self.admin, remarks="Closed by admin audit")
        complaint.refresh_from_db()
        self.assertEqual(complaint.status, Complaint.STATUS_CLOSED)

    def test_invalid_transition_submitted_to_resolved_raises_error(self):
        """
        Illegal jump: SUBMITTED -> RESOLVED directly is rejected.
        """
        complaint = Complaint.objects.create(
            title="Direct jump test", description="desc", category=self.category_elec,
            location="Hall", priority=Complaint.PRIORITY_LOW, submitted_by=self.student
        )
        with self.assertRaises(InvalidStatusTransitionError):
            complaint.transition_to(Complaint.STATUS_RESOLVED, user=self.staff1, remarks="Attempt direct fix")

    def test_invalid_transition_student_cannot_start_work(self):
        """
        Illegal actor: Student trying ASSIGNED -> IN_PROGRESS is rejected.
        """
        complaint = Complaint.objects.create(
            title="Student transition test", description="desc", category=self.category_elec,
            location="Hall", priority=Complaint.PRIORITY_LOW, submitted_by=self.student
        )
        complaint.transition_to(Complaint.STATUS_ASSIGNED, user=self.admin, assigned_to_user=self.staff1)
        
        with self.assertRaises(InvalidStatusTransitionError):
            complaint.transition_to(Complaint.STATUS_IN_PROGRESS, user=self.student)

    def test_invalid_transition_staff_cannot_assign(self):
        """
        Illegal actor: Staff trying SUBMITTED -> ASSIGNED is rejected.
        """
        complaint = Complaint.objects.create(
            title="Staff assign test", description="desc", category=self.category_elec,
            location="Hall", priority=Complaint.PRIORITY_LOW, submitted_by=self.student
        )
        with self.assertRaises(InvalidStatusTransitionError):
            complaint.transition_to(Complaint.STATUS_ASSIGNED, user=self.staff1, assigned_to_user=self.staff2)

    def test_invalid_transition_resolved_requires_remarks(self):
        """
        Illegal transition: IN_PROGRESS -> RESOLVED without remarks is rejected.
        """
        complaint = Complaint.objects.create(
            title="Remarks test", description="desc", category=self.category_elec,
            location="Hall", priority=Complaint.PRIORITY_LOW, submitted_by=self.student
        )
        complaint.transition_to(Complaint.STATUS_ASSIGNED, user=self.admin, assigned_to_user=self.staff1)
        complaint.transition_to(Complaint.STATUS_IN_PROGRESS, user=self.staff1)

        with self.assertRaises(InvalidStatusTransitionError):
            complaint.transition_to(Complaint.STATUS_RESOLVED, user=self.staff1, remarks="")


class StudentViewsAndScopingTests(TestCase):
    """
    Test suite for Student views, validation, and IDOR protection.
    """
    def setUp(self):
        self.client = Client()

        # Seed students
        self.student_a = User.objects.create_user(username='student_alice', password='password123')
        self.student_a.profile.role = Profile.ROLE_STUDENT
        self.student_a.profile.save()

        self.student_b = User.objects.create_user(username='student_bob', password='password123')
        self.student_b.profile.role = Profile.ROLE_STUDENT
        self.student_b.profile.save()

        self.staff = User.objects.create_user(username='staff_mark', password='password123')
        self.staff.profile.role = Profile.ROLE_STAFF
        self.staff.profile.save()

        self.admin = User.objects.create_user(username='admin_boss', password='password123')
        self.admin.profile.role = Profile.ROLE_ADMIN
        self.admin.profile.save()

        self.category = Category.objects.create(name='Plumbing', description='Water pipes and sinks')

    def _generate_test_image(self):
        file = io.BytesIO()
        image = Image.new('RGBA', size=(100, 100), color=(155, 0, 0))
        image.save(file, 'png')
        file.seek(0)
        return SimpleUploadedFile('test_photo.png', file.read(), content_type='image/png')

    def test_student_dashboard_statistics(self):
        self.client.login(username='student_alice', password='password123')

        # Create complaints for Alice
        Complaint.objects.create(
            title="Sink leak", description="Leaking sink", category=self.category,
            location="Washroom 1", priority=Complaint.PRIORITY_MEDIUM,
            status=Complaint.STATUS_SUBMITTED, submitted_by=self.student_a
        )
        Complaint.objects.create(
            title="Pipe burst", description="High pressure pipe burst", category=self.category,
            location="Washroom 2", priority=Complaint.PRIORITY_URGENT,
            status=Complaint.STATUS_IN_PROGRESS, submitted_by=self.student_a
        )

        # Create a complaint for Bob (should not count for Alice)
        Complaint.objects.create(
            title="Bob's faucet", description="Dripping faucet", category=self.category,
            location="Washroom 3", priority=Complaint.PRIORITY_LOW,
            status=Complaint.STATUS_SUBMITTED, submitted_by=self.student_b
        )

        response = self.client.get(reverse('dashboard:student_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_count'], 2)
        self.assertEqual(response.context['pending_count'], 2)
        self.assertEqual(response.context['in_progress_count'], 1)
        self.assertEqual(len(response.context['recent_complaints']), 2)

    def test_student_complaint_creation_flow(self):
        self.client.login(username='student_alice', password='password123')
        create_url = reverse('complaints:student_complaint_create')

        test_image = self._generate_test_image()
        payload = {
            'title': 'Restroom water tap broken',
            'category': self.category.id,
            'location': 'Block C, Ground Floor Restroom',
            'priority': Complaint.PRIORITY_HIGH,
            'description': 'Water tap is loose and overflowing onto the floor.',
            'image': test_image
        }

        response = self.client.post(create_url, data=payload, follow=True)
        self.assertEqual(response.status_code, 200)

        # Verify database record
        complaint = Complaint.objects.get(title='Restroom water tap broken')
        self.assertEqual(complaint.submitted_by, self.student_a)
        self.assertEqual(complaint.status, Complaint.STATUS_SUBMITTED)
        self.assertTrue(complaint.complaint_id.startswith('CMP-'))
        self.assertTrue(bool(complaint.image))

        # Verify initial history entry was created
        history_entry = complaint.history.first()
        self.assertIsNotNone(history_entry)
        self.assertEqual(history_entry.new_status, Complaint.STATUS_SUBMITTED)
        self.assertEqual(history_entry.changed_by, self.student_a)

    def test_required_fields_validation(self):
        """
        Verify empty complaint form submission fails validation with field-level errors.
        """
        self.client.login(username='student_alice', password='password123')
        create_url = reverse('complaints:student_complaint_create')

        response = self.client.post(create_url, data={})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'title', 'This field is required.')
        self.assertFormError(response.context['form'], 'category', 'This field is required.')
        self.assertFormError(response.context['form'], 'location', 'This field is required.')
        self.assertFormError(response.context['form'], 'description', 'This field is required.')

    def test_student_list_scoping_and_search_filters(self):
        self.client.login(username='student_alice', password='password123')

        c1 = Complaint.objects.create(
            title="Electrical spark in Lab 4", description="Sparking wire", category=self.category,
            location="Lab 4", priority=Complaint.PRIORITY_URGENT, status=Complaint.STATUS_SUBMITTED,
            submitted_by=self.student_a
        )
        c2 = Complaint.objects.create(
            title="Broken chair in Room 101", description="Chair leg broken", category=self.category,
            location="Room 101", priority=Complaint.PRIORITY_LOW, status=Complaint.STATUS_CLOSED,
            submitted_by=self.student_a
        )
        c3 = Complaint.objects.create(
            title="Bob's private complaint", description="Confidential issue", category=self.category,
            location="Hostel 2", priority=Complaint.PRIORITY_HIGH, status=Complaint.STATUS_SUBMITTED,
            submitted_by=self.student_b
        )

        list_url = reverse('complaints:student_complaint_list')

        # 1. Base list: Alice should see c1 and c2, but NOT c3
        res = self.client.get(list_url)
        self.assertEqual(res.status_code, 200)
        complaint_ids = [c.complaint_id for c in res.context['complaints']]
        self.assertIn(c1.complaint_id, complaint_ids)
        self.assertIn(c2.complaint_id, complaint_ids)
        self.assertNotIn(c3.complaint_id, complaint_ids)

        # 2. Search filter
        res_search = self.client.get(list_url, {'q': 'spark'})
        self.assertEqual(res_search.context['page_obj'].paginator.count, 1)
        self.assertEqual(res_search.context['complaints'][0].complaint_id, c1.complaint_id)

        # 3. Status filter
        res_status = self.client.get(list_url, {'status': 'CLOSED'})
        self.assertEqual(res_status.context['page_obj'].paginator.count, 1)
        self.assertEqual(res_status.context['complaints'][0].complaint_id, c2.complaint_id)

    def test_student_cannot_view_others_complaint_detail(self):
        bobs_complaint = Complaint.objects.create(
            title="Bob's private ticket", description="Secret", category=self.category,
            location="Hostel A", submitted_by=self.student_b
        )

        self.client.login(username='student_alice', password='password123')
        detail_url = reverse('complaints:student_complaint_detail', kwargs={'complaint_id': bobs_complaint.complaint_id})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 404)

    def test_student_can_close_resolved_complaint(self):
        complaint = Complaint.objects.create(
            title="Broken tap", description="Leaking", category=self.category,
            location="Block A", submitted_by=self.student_a
        )
        complaint.transition_to('ASSIGNED', user=self.admin, assigned_to_user=self.staff)
        complaint.transition_to('IN_PROGRESS', user=self.staff)
        complaint.transition_to('RESOLVED', user=self.staff, remarks="Fixed tap washer.")

        self.client.login(username='student_alice', password='password123')
        close_url = reverse('complaints:student_complaint_close', kwargs={'complaint_id': complaint.complaint_id})
        
        response = self.client.post(close_url, data={'remarks': 'Verified working properly.'}, follow=True)
        self.assertEqual(response.status_code, 200)

        complaint.refresh_from_db()
        self.assertEqual(complaint.status, Complaint.STATUS_CLOSED)
        self.assertIsNotNone(complaint.closed_at)

        # Verify history
        last_history = complaint.history.first()
        self.assertEqual(last_history.old_status, Complaint.STATUS_RESOLVED)
        self.assertEqual(last_history.new_status, Complaint.STATUS_CLOSED)
        self.assertEqual(last_history.changed_by, self.student_a)
        self.assertEqual(last_history.remarks, 'Verified working properly.')
