from django.urls import path
from . import views

app_name = 'complaints'

urlpatterns = [
    # Student Complaint Routes
    path('create/', views.student_complaint_create, name='student_complaint_create'),
    path('my/', views.student_complaint_list, name='student_complaint_list'),
    path('<str:complaint_id>/', views.student_complaint_detail, name='student_complaint_detail'),
    path('<str:complaint_id>/close/', views.student_complaint_close, name='student_complaint_close'),
]
