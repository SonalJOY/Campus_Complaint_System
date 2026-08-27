from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import Profile
from complaints.models import Category


class Command(BaseCommand):
    help = "Seed database with default categories and demonstration users for each role."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding campus categories..."))
        
        categories = [
            ("Electrical", "Lighting, circuit breakers, power sockets, wiring issues"),
            ("Plumbing", "Water leakage, blocked drains, restroom fixtures, taps"),
            ("Furniture", "Desks, chairs, whiteboards, podiums, broken cupboards"),
            ("IT/Network", "Wi-Fi access points, ethernet LAN ports, router issues"),
            ("Classroom Equipment", "Projectors, smartboards, audio mics, speakers"),
            ("Laboratory Equipment", "Oscilloscopes, microscopes, fume hoods, power supplies"),
            ("Cleanliness", "Waste disposal, dustbins, hallway cleaning, sanitation"),
            ("Other", "General campus infrastructure and miscellaneous maintenance"),
        ]

        for name, desc in categories:
            cat, created = Category.objects.get_or_create(
                name=name,
                defaults={'description': desc, 'is_active': True}
            )
            status_text = "Created" if created else "Exists"
            self.stdout.write(f"  [{status_text}] Category: {name}")

        self.stdout.write(self.style.NOTICE("\nSeeding demonstration users for RBAC..."))

        users_data = [
            {
                'username': 'student_demo',
                'email': 'student@campus.edu',
                'first_name': 'Alex',
                'last_name': 'Student',
                'role': Profile.ROLE_STUDENT,
                'phone': '+1-555-0101',
                'is_staff': False,
                'is_superuser': False,
            },
            {
                'username': 'staff_demo',
                'email': 'staff@campus.edu',
                'first_name': 'Robert',
                'last_name': 'Technician',
                'role': Profile.ROLE_STAFF,
                'phone': '+1-555-0202',
                'is_staff': False,
                'is_superuser': False,
            },
            {
                'username': 'admin_demo',
                'email': 'admin@campus.edu',
                'first_name': 'Clara',
                'last_name': 'Administrator',
                'role': Profile.ROLE_ADMIN,
                'phone': '+1-555-0303',
                'is_staff': True,
                'is_superuser': False,
            },
            {
                'username': 'superadmin',
                'email': 'superadmin@campus.edu',
                'first_name': 'Super',
                'last_name': 'Admin',
                'role': Profile.ROLE_ADMIN,
                'phone': '+1-555-0000',
                'is_staff': True,
                'is_superuser': True,
            },
        ]

        for udata in users_data:
            username = udata['username']
            user = User.objects.filter(username=username).first()
            if not user:
                if udata['is_superuser']:
                    user = User.objects.create_superuser(
                        username=username,
                        email=udata['email'],
                        password='password123',
                        first_name=udata['first_name'],
                        last_name=udata['last_name']
                    )
                else:
                    user = User.objects.create_user(
                        username=username,
                        email=udata['email'],
                        password='password123',
                        first_name=udata['first_name'],
                        last_name=udata['last_name'],
                        is_staff=udata['is_staff']
                    )
                user.profile.role = udata['role']
                user.profile.phone = udata['phone']
                user.profile.save()
                self.stdout.write(self.style.SUCCESS(f"  [Created] {username} ({udata['role']}) / password123"))
            else:
                user.set_password('password123')
                user.first_name = udata['first_name']
                user.last_name = udata['last_name']
                user.is_staff = udata['is_staff']
                user.is_superuser = udata['is_superuser']
                user.save()
                user.profile.role = udata['role']
                user.profile.phone = udata['phone']
                user.profile.save()
                self.stdout.write(f"  [Updated] {username} ({udata['role']}) / password123")

        self.stdout.write(self.style.SUCCESS("\nSeeding complete!"))
