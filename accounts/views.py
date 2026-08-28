from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.http import url_has_allowed_host_and_scheme
from .forms import StudentRegistrationForm, LoginForm
from .models import Profile


def register_view(request):
    """
    Public student registration view.
    """
    if request.user.is_authenticated:
        return redirect('accounts:redirect_dashboard')

    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(
                request,
                f"Welcome, {user.first_name or user.username}! Your student account has been created successfully. Please log in below."
            )
            return redirect('accounts:login')
    else:
        form = StudentRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    """
    Login view supporting username or email authentication.
    Redirects to role-specific dashboard upon successful authentication.
    """
    if request.user.is_authenticated:
        return redirect('accounts:redirect_dashboard')

    redirect_to = request.GET.get('next', '')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            identifier = form.cleaned_data['username_or_email'].strip()
            password = form.cleaned_data['password']
            remember_me = form.cleaned_data.get('remember_me', False)

            # Try direct username authentication first
            user = authenticate(request, username=identifier, password=password)

            # If failed, attempt matching email
            if user is None:
                try:
                    user_obj = User.objects.get(email__iexact=identifier)
                    user = authenticate(request, username=user_obj.username, password=password)
                except (User.DoesNotExist, User.MultipleObjectsReturned):
                    user = None

            if user is not None:
                if not user.is_active:
                    form.add_error(None, "This account is currently deactivated. Please contact campus administration.")
                else:
                    login(request, user)

                    # Manage session expiry
                    if not remember_me:
                        request.session.set_expiry(0)  # Browser close
                    else:
                        request.session.set_expiry(1209600)  # 2 weeks

                    messages.success(
                        request,
                        f"Welcome back, {user.get_full_name() or user.username}!"
                    )

                    # Check next redirect target safety
                    if redirect_to and url_has_allowed_host_and_scheme(redirect_to, allowed_hosts={request.get_host()}):
                        return redirect(redirect_to)
                    
                    return redirect('accounts:redirect_dashboard')
            else:
                user_match = User.objects.filter(username__iexact=identifier).first() or User.objects.filter(email__iexact=identifier).first()
                if user_match and user_match.check_password(password) and not user_match.is_active:
                    form.add_error(None, "This account is currently deactivated. Please contact campus administration.")
                else:
                    form.add_error(None, "Invalid username/email or password. Please verify your credentials.")
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {
        'form': form,
        'next': redirect_to
    })


def logout_view(request):
    """
    Logs the user out and redirects to the landing page.
    """
    if request.user.is_authenticated:
        logout(request)
        messages.info(request, "You have been logged out successfully.")
    return redirect('home')


@login_required
def redirect_dashboard(request):
    """
    Intelligently routes users to their role-specific dashboard:
    STUDENT -> /dashboard/student/
    STAFF   -> /dashboard/staff/
    ADMIN   -> /dashboard/admin/
    """
    profile = getattr(request.user, 'profile', None)
    role = profile.role if profile else None

    if role == Profile.ROLE_STUDENT:
        return redirect('dashboard:student_dashboard')
    elif role == Profile.ROLE_STAFF:
        return redirect('dashboard:staff_dashboard')
    elif role == Profile.ROLE_ADMIN or request.user.is_superuser:
        return redirect('dashboard:admin_dashboard')
    else:
        # Fallback default
        return redirect('home')
