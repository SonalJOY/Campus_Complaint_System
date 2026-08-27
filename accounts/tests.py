from django.test import TestCase
from django.contrib.auth.models import User
from .models import Profile


class AccountsModelTests(TestCase):
    def test_profile_auto_creation_and_defaults(self):
        user = User.objects.create_user(username='john_doe', password='password123')
        self.assertTrue(hasattr(user, 'profile'))
        self.assertEqual(user.profile.role, Profile.ROLE_STUDENT)
        self.assertTrue(user.profile.is_student)
        self.assertFalse(user.profile.is_staff_member)
        self.assertFalse(user.profile.is_admin_user)

    def test_profile_role_assignment(self):
        staff_user = User.objects.create_user(username='tech_staff', password='password123')
        staff_user.profile.role = Profile.ROLE_STAFF
        staff_user.profile.phone = "9876543210"
        staff_user.profile.save()

        self.assertEqual(staff_user.profile.role, Profile.ROLE_STAFF)
        self.assertTrue(staff_user.profile.is_staff_member)
        self.assertEqual(staff_user.profile.phone, "9876543210")
        self.assertEqual(str(staff_user.profile), "tech_staff (Maintenance Staff)")
