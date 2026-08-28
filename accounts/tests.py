from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Profile


class AccountsModelTests(TestCase):
    """
    Unit tests for Profile model, roles, and helper properties.
    """
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

    def test_admin_role_property(self):
        admin_user = User.objects.create_user(username='admin_role_user', password='password123')
        admin_user.profile.role = Profile.ROLE_ADMIN
        admin_user.profile.save()

        self.assertTrue(admin_user.profile.is_admin_user)
        self.assertFalse(admin_user.profile.is_student)
        self.assertFalse(admin_user.profile.is_staff_member)


class AuthenticationAndRBACTests(TestCase):
    """
    Comprehensive test suite for login, logout, registration, and RBAC redirects.
    """
    def setUp(self):
        self.client = Client()

        # Student user
        self.student = User.objects.create_user(
            username='student_test',
            email='student_test@campus.edu',
            password='password123'
        )
        self.student.profile.role = Profile.ROLE_STUDENT
        self.student.profile.save()

        # Staff user
        self.staff = User.objects.create_user(
            username='staff_test',
            email='staff_test@campus.edu',
            password='password123'
        )
        self.staff.profile.role = Profile.ROLE_STAFF
        self.staff.profile.save()

        # Admin user
        self.admin = User.objects.create_user(
            username='admin_test',
            email='admin_test@campus.edu',
            password='password123'
        )
        self.admin.profile.role = Profile.ROLE_ADMIN
        self.admin.profile.save()

    def test_student_public_registration_forces_student_role(self):
        url = reverse('accounts:register')
        payload = {
            'username': 'new_student',
            'first_name': 'Jane',
            'last_name': 'Doe',
            'email': 'jane@campus.edu',
            'phone': '123-456-7890',
            'password': 'StrongPassword123!',
            'confirm_password': 'StrongPassword123!',
            'role': 'ADMIN'  # Attempting to inject ADMIN role
        }
        response = self.client.post(url, data=payload, follow=True)
        self.assertEqual(response.status_code, 200)

        # Confirm user was created with STUDENT role regardless of payload
        user = User.objects.get(username='new_student')
        self.assertEqual(user.profile.role, Profile.ROLE_STUDENT)
        self.assertEqual(user.first_name, 'Jane')

    def test_registration_password_mismatch(self):
        url = reverse('accounts:register')
        payload = {
            'username': 'mismatch_user',
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'mismatch@campus.edu',
            'password': 'Password123!',
            'confirm_password': 'DifferentPassword123!'
        }
        response = self.client.post(url, data=payload)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'confirm_password', 'Passwords do not match. Please verify and re-type.')
        self.assertFalse(User.objects.filter(username='mismatch_user').exists())

    def test_registration_duplicate_username_and_email_rejected(self):
        url = reverse('accounts:register')
        
        # Duplicate username
        res1 = self.client.post(url, {
            'username': 'student_test',
            'first_name': 'Another',
            'last_name': 'Student',
            'email': 'unique@campus.edu',
            'password': 'StrongPassword123!',
            'confirm_password': 'StrongPassword123!'
        })
        self.assertEqual(res1.status_code, 200)
        self.assertFormError(res1.context['form'], 'username', 'This username is already taken. Please choose a different one.')

        # Duplicate email
        res2 = self.client.post(url, {
            'username': 'unique_user',
            'first_name': 'Another',
            'last_name': 'Student',
            'email': 'student_test@campus.edu',
            'password': 'StrongPassword123!',
            'confirm_password': 'StrongPassword123!'
        })
        self.assertEqual(res2.status_code, 200)
        self.assertFormError(res2.context['form'], 'email', 'An account with this email address already exists.')

    def test_login_with_username_and_email(self):
        login_url = reverse('accounts:login')

        # 1. Test login via username
        res1 = self.client.post(login_url, {
            'username_or_email': 'student_test',
            'password': 'password123'
        }, follow=True)
        self.assertEqual(res1.status_code, 200)
        self.assertTrue(res1.context['user'].is_authenticated)
        self.assertEqual(res1.redirect_chain[-1][0], reverse('dashboard:student_dashboard'))
        self.client.logout()

        # 2. Test login via email
        res2 = self.client.post(login_url, {
            'username_or_email': 'staff_test@campus.edu',
            'password': 'password123'
        }, follow=True)
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.context['user'].is_authenticated)
        self.assertEqual(res2.redirect_chain[-1][0], reverse('dashboard:staff_dashboard'))
        self.client.logout()

    def test_invalid_password_rejected(self):
        login_url = reverse('accounts:login')
        response = self.client.post(login_url, {
            'username_or_email': 'student_test',
            'password': 'completely_wrong_password'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['user'].is_authenticated)
        self.assertContains(response, "Invalid username/email or password")

    def test_nonexistent_user_login_rejected(self):
        login_url = reverse('accounts:login')
        response = self.client.post(login_url, {
            'username_or_email': 'nonexistent_user',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username/email or password")

    def test_deactivated_user_login_blocked(self):
        self.student.is_active = False
        self.student.save()

        login_url = reverse('accounts:login')
        response = self.client.post(login_url, {
            'username_or_email': 'student_test',
            'password': 'password123'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['user'].is_authenticated)
        self.assertContains(response, "This account is currently deactivated")

    def test_logout_redirects_home(self):
        self.client.login(username='student_test', password='password123')
        response = self.client.get(reverse('accounts:logout'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['user'].is_authenticated)

    def test_role_based_dashboard_redirects(self):
        redirect_url = reverse('accounts:redirect_dashboard')

        # 1. Student redirect
        self.client.login(username='student_test', password='password123')
        res_student = self.client.get(redirect_url)
        self.assertRedirects(res_student, reverse('dashboard:student_dashboard'))
        self.client.logout()

        # 2. Staff redirect
        self.client.login(username='staff_test', password='password123')
        res_staff = self.client.get(redirect_url)
        self.assertRedirects(res_staff, reverse('dashboard:staff_dashboard'))
        self.client.logout()

        # 3. Admin redirect
        self.client.login(username='admin_test', password='password123')
        res_admin = self.client.get(redirect_url)
        self.assertRedirects(res_admin, reverse('dashboard:admin_dashboard'))
        self.client.logout()

    def test_unauthorized_role_access_returns_403(self):
        # 1. Student attempting to access Staff and Admin dashboards
        self.client.login(username='student_test', password='password123')
        
        res_staff_page = self.client.get(reverse('dashboard:staff_dashboard'))
        self.assertEqual(res_staff_page.status_code, 403)
        self.assertContains(res_staff_page, "403 - Access Restricted", status_code=403)

        res_admin_page = self.client.get(reverse('dashboard:admin_dashboard'))
        self.assertEqual(res_admin_page.status_code, 403)
        self.assertContains(res_admin_page, "403 - Access Restricted", status_code=403)

        # But Student can access Student dashboard
        res_own_page = self.client.get(reverse('dashboard:student_dashboard'))
        self.assertEqual(res_own_page.status_code, 200)
        self.client.logout()

        # 2. Staff attempting to access Student and Admin dashboards
        self.client.login(username='staff_test', password='password123')
        res_student_page = self.client.get(reverse('dashboard:student_dashboard'))
        self.assertEqual(res_student_page.status_code, 403)

        res_admin_page = self.client.get(reverse('dashboard:admin_dashboard'))
        self.assertEqual(res_admin_page.status_code, 403)
        self.client.logout()

    def test_anonymous_access_redirects_to_login(self):
        res = self.client.get(reverse('dashboard:student_dashboard'))
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.url.startswith(reverse('accounts:login')))
