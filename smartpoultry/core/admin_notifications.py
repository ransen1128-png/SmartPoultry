"""The administrator bell combines pending recovery requests and feedback."""
from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.cache import never_cache

from .models import Feedback, PasswordResetRequest


def is_administrator(user):
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


def bell_data():
    pending = PasswordResetRequest.objects.filter(status='pending')
    feedback_count = Feedback.objects.filter(status='new').count()
    reset_count = pending.count()
    return {
        'count': reset_count + feedback_count,
        'reset_count': reset_count,
        'feedback_count': feedback_count,
        'requests': [{
            'id': item.pk,
            'username': item.user.username,
            'url': reverse('admin_password_reset_requests') + f'#request-{item.pk}',
        } for item in pending.select_related('user')[:5]],
    }


def context(request):
    return {'admin_notifications': bell_data()} if is_administrator(getattr(request, 'user', None)) else {}


@user_passes_test(is_administrator, login_url='login')
@never_cache
def poll(request):
    return JsonResponse(bell_data())


@user_passes_test(is_administrator, login_url='login')
@never_cache
def requests_page(request):
    requests = PasswordResetRequest.objects.select_related('user', 'resolved_by')
    return render(request, 'admin_password_reset_requests.html', {
        'pending_requests': requests.filter(status='pending'),
        'resolved_requests': requests.filter(status='resolved')[:50],
    })
