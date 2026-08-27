from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from accounts.models import Profile
from .models import Category, Complaint, ComplaintHistory, InvalidStatusTransitionError


class ComplaintModelAndStateMachineTests(TestCase):
    def setUp(self):
        # Create users with different roles
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

        # Create Category
        self.category_elec = Category.objects.create(
            name='Electrical',
            description='Power outlets, lighting, wiring issues'
        )

    def test_complaint_id_auto_generation(self):
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

    def test_full_valid_state_machine_lifecycle(self):
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
        self.assertEqual(history_records[2].remarks, "Replaced 45uF capacitor and tested airflow temperature.")

        self.assertEqual(history_records[3].old_status, Complaint.STATUS_RESOLVED)
        self.assertEqual(history_records[3].new_status, Complaint.STATUS_CLOSED)
        self.assertEqual(history_records[3].changed_by, self.student)

    def test_non_admin_cannot_assign(self):
        complaint = Complaint.objects.create(
            title="Broken socket",
            description="Socket loose",
            category=self.category_elec,
            location="Room 201",
            submitted_by=self.student
        )
        with self.assertRaises(InvalidStatusTransitionError) as ctx:
            complaint.transition_to(
                new_status=Complaint.STATUS_ASSIGNED,
                user=self.student,
                assigned_to_user=self.staff1
            )
        self.assertIn("Only administrators", str(ctx.exception))

    def test_cannot_assign_to_non_staff(self):
        complaint = Complaint.objects.create(
            title="Broken socket",
            description="Socket loose",
            category=self.category_elec,
            location="Room 201",
            submitted_by=self.student
        )
        with self.assertRaises(InvalidStatusTransitionError) as ctx:
            complaint.transition_to(
                new_status=Complaint.STATUS_ASSIGNED,
                user=self.admin,
                assigned_to_user=self.other_student
            )
        self.assertIn("STAFF role", str(ctx.exception))

    def test_unassigned_staff_cannot_move_to_in_progress(self):
        complaint = Complaint.objects.create(
            title="Broken socket",
            description="Socket loose",
            category=self.category_elec,
            location="Room 201",
            submitted_by=self.student
        )
        complaint.transition_to(
            new_status=Complaint.STATUS_ASSIGNED,
            user=self.admin,
            assigned_to_user=self.staff1
        )
        with self.assertRaises(InvalidStatusTransitionError) as ctx:
            complaint.transition_to(
                new_status=Complaint.STATUS_IN_PROGRESS,
                user=self.staff2
            )
        self.assertIn("Only the assigned staff", str(ctx.exception))

    def test_resolution_requires_remarks(self):
        complaint = Complaint.objects.create(
            title="Broken socket",
            description="Socket loose",
            category=self.category_elec,
            location="Room 201",
            submitted_by=self.student
        )
        complaint.transition_to(
            new_status=Complaint.STATUS_ASSIGNED,
            user=self.admin,
            assigned_to_user=self.staff1
        )
        complaint.transition_to(
            new_status=Complaint.STATUS_IN_PROGRESS,
            user=self.staff1
        )
        with self.assertRaises(InvalidStatusTransitionError) as ctx:
            complaint.transition_to(
                new_status=Complaint.STATUS_RESOLVED,
                user=self.staff1,
                remarks=""
            )
        self.assertIn("Resolution remarks are required", str(ctx.exception))

    def test_other_student_cannot_close_complaint(self):
        complaint = Complaint.objects.create(
            title="Broken socket",
            description="Socket loose",
            category=self.category_elec,
            location="Room 201",
            submitted_by=self.student
        )
        complaint.transition_to(
            new_status=Complaint.STATUS_ASSIGNED,
            user=self.admin,
            assigned_to_user=self.staff1
        )
        complaint.transition_to(
            new_status=Complaint.STATUS_IN_PROGRESS,
            user=self.staff1
        )
        complaint.transition_to(
            new_status=Complaint.STATUS_RESOLVED,
            user=self.staff1,
            remarks="Fixed"
        )
        with self.assertRaises(InvalidStatusTransitionError) as ctx:
            complaint.transition_to(
                new_status=Complaint.STATUS_CLOSED,
                user=self.other_student
            )
        self.assertIn("Only the student who submitted", str(ctx.exception))

    def test_invalid_arbitrary_transition_rejected(self):
        complaint = Complaint.objects.create(
            title="Broken socket",
            description="Socket loose",
            category=self.category_elec,
            location="Room 201",
            submitted_by=self.student
        )
        # Attempting direct jump from SUBMITTED to RESOLVED
        with self.assertRaises(InvalidStatusTransitionError) as ctx:
            complaint.transition_to(
                new_status=Complaint.STATUS_RESOLVED,
                user=self.admin,
                remarks="Bypassing steps"
            )
        self.assertIn("Invalid status transition", str(ctx.exception))
