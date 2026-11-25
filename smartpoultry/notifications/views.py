from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Notification, Alert, NotificationPreference
from .serializers import NotificationSerializer, AlertSerializer, NotificationPreferenceSerializer
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils.timesince import timesince
from django.views.decorators.http import require_GET


@login_required(login_url='login')
@require_GET
def notification_preview(request):
    """Read-only header preview, restricted to the signed-in account."""
    notifications = Notification.objects.filter(user=request.user)
    return JsonResponse({'unread_count': notifications.filter(is_read=False).count(), 'results': [
        {'id': item.pk, 'title': item.title, 'message': item.message, 'is_read': item.is_read,
         'created_at': item.created_at.isoformat(), 'age': timesince(item.created_at) + ' ago'}
        for item in notifications.order_by('-created_at', '-pk')[:5]
    ]})


class NotificationViewSet(viewsets.ModelViewSet):
    """ViewSet for notifications."""
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['post'])
    def mark_as_read(self, request):
        """Mark all notifications as read."""
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'status': 'notifications marked as read'})
    
    @action(detail=True, methods=['post'])
    def read(self, request, pk=None):
        """Mark specific notification as read."""
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response({'status': 'notification marked as read'})


class AlertViewSet(viewsets.ModelViewSet):
    """ViewSet for alerts."""
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Alert.objects.filter(farm__owner=self.request.user)
    
    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """Acknowledge an alert."""
        alert = self.get_object()
        alert.status = 'acknowledged'
        alert.save()
        return Response({'status': 'alert acknowledged'})
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve an alert."""
        alert = self.get_object()
        alert.status = 'resolved'
        alert.save()
        return Response({'status': 'alert resolved'})


class NotificationPreferenceViewSet(viewsets.ModelViewSet):
    """ViewSet for notification preferences."""
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return NotificationPreference.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Each account has one set of preferences; saving again updates it.
        serializer.instance, _ = NotificationPreference.objects.get_or_create(user=self.request.user)
        serializer.save(user=self.request.user)
