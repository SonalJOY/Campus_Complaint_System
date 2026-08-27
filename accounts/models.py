from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    """
    User Profile Extension.
    
    Design Decision:
    We use a Profile model with a One-to-One relationship linked to Django's built-in User.
    This maintains seamless compatibility with standard Django authentication, sessions,
    and the built-in admin, while cleanly isolating custom campus roles and phone metadata.
    """
    
    ROLE_STUDENT = 'STUDENT'
    ROLE_STAFF = 'STAFF'
    ROLE_ADMIN = 'ADMIN'
    
    ROLE_CHOICES = [
        (ROLE_STUDENT, 'Student'),
        (ROLE_STAFF, 'Maintenance Staff'),
        (ROLE_ADMIN, 'Administrator'),
    ]
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        help_text="Underlying Django auth user account"
    )
    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default=ROLE_STUDENT,
        help_text="Role-Based Access Control level"
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Contact phone number for communication"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when profile was created"
    )

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    @property
    def is_student(self):
        return self.role == self.ROLE_STUDENT

    @property
    def is_staff_member(self):
        return self.role == self.ROLE_STAFF

    @property
    def is_admin_user(self):
        return self.role == self.ROLE_ADMIN or self.user.is_superuser


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """
    Automatically creates a corresponding Profile whenever a new User is created.
    """
    if created:
        Profile.objects.create(user=instance)
    else:
        # Ensure profile exists for existing users
        Profile.objects.get_or_create(user=instance)
