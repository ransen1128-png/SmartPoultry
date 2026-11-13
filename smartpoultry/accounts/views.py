from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated,IsAdminUser
from rest_framework.exceptions import PermissionDenied
from .models import UserProfile, UserRole
from .serializers import UserProfileSerializer, UserRoleSerializer


class UserProfileViewSet(viewsets.ModelViewSet):
    """ViewSet for user management."""
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        permissions=[IsAuthenticated,IsAdminUser] if self.action in ('create','destroy') else [IsAuthenticated]
        return [permission() for permission in permissions]

    def get_queryset(self):
        if self.request.user.is_staff or self.request.user.is_superuser:
            return UserProfile.objects.order_by('pk')
        return UserProfile.objects.filter(pk=self.request.user.pk).order_by('pk')

    def perform_update(self,serializer):
        if serializer.instance.is_superuser and not self.request.user.is_superuser:
            raise PermissionDenied('Only a superuser can change a superuser account.')
        serializer.save()

    def perform_destroy(self,instance):
        if instance.pk==self.request.user.pk:
            raise PermissionDenied('You cannot delete your own account.')
        if instance.is_superuser and not self.request.user.is_superuser:
            raise PermissionDenied('Only a superuser can delete a superuser account.')
        instance.delete()


class UserRoleViewSet(viewsets.ModelViewSet):
    """ViewSet for user roles."""
    queryset = UserRole.objects.all()
    serializer_class = UserRoleSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        permissions=[IsAuthenticated] if self.action in ('list','retrieve') else [IsAuthenticated,IsAdminUser]
        return [permission() for permission in permissions]
