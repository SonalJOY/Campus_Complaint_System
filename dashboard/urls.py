# pyrefly: ignore [missing-import]
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Dashboard Landing Pages
    path('student/', views.student_dashboard, name='student_dashboard'),
    path('staff/', views.staff_dashboard, name='staff_dashboard'),
    path('admin/', views.admin_dashboard, name='admin_dashboard'),

    # Staff Work Order Routes
    path('staff/tasks/', views.staff_complaint_list, name='staff_complaint_list'),
    path('staff/tasks/<str:complaint_id>/', views.staff_complaint_detail, name='staff_complaint_detail'),
    path('staff/tasks/<str:complaint_id>/start/', views.staff_complaint_start_work, name='staff_complaint_start_work'),
    path('staff/tasks/<str:complaint_id>/resolve/', views.staff_complaint_resolve, name='staff_complaint_resolve'),

    # Admin Complaint Management Routes
    path('admin/complaints/', views.admin_complaint_list, name='admin_complaint_list'),
    path('admin/complaints/<str:complaint_id>/', views.admin_complaint_detail, name='admin_complaint_detail'),
    path('admin/complaints/<str:complaint_id>/force-close/', views.admin_complaint_force_close, name='admin_complaint_force_close'),

    # Admin Category CRUD Routes
    path('admin/categories/', views.admin_category_list, name='admin_category_list'),
    path('admin/categories/create/', views.admin_category_create, name='admin_category_create'),
    path('admin/categories/<int:pk>/edit/', views.admin_category_edit, name='admin_category_edit'),
    path('admin/categories/<int:pk>/toggle/', views.admin_category_toggle, name='admin_category_toggle'),

    # Admin User Directory & Management Routes
    path('admin/users/', views.admin_user_list, name='admin_user_list'),
    path('admin/users/<int:user_id>/toggle/', views.admin_user_toggle_status, name='admin_user_toggle_status'),
]
