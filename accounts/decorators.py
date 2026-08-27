from functools import wraps
from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import render
from django.core.exceptions import PermissionDenied


def role_required(allowed_roles):
    """
    Decorator for views that checks whether a user is authenticated and possesses
    one of the specified roles ('STUDENT', 'STAFF', 'ADMIN').
    
    If not authenticated -> redirects to login with next parameter.
    If unauthorized -> renders a friendly HTTP 403 Forbidden page.
    """
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(
                    request.get_full_path(),
                    settings.LOGIN_URL
                )

            # Check role on profile
            user_profile = getattr(request.user, 'profile', None)
            user_role = user_profile.role if user_profile else None
            
            # Superusers always have admin rights
            is_authorized = (user_role in allowed_roles) or (
                'ADMIN' in allowed_roles and request.user.is_superuser
            )

            if not is_authorized:
                context = {
                    'user_role': user_role,
                    'allowed_roles': allowed_roles,
                    'message': f"Access restricted. This page requires one of the following roles: {', '.join(allowed_roles)}."
                }
                return render(request, '403.html', context, status=403)

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def student_required(view_func):
    return role_required(['STUDENT'])(view_func)


def staff_required(view_func):
    return role_required(['STAFF'])(view_func)


def admin_required(view_func):
    return role_required(['ADMIN'])(view_func)
