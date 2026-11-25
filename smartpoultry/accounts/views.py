from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated,IsAdminUser
from rest_framework.exceptions import PermissionDenied
from core.account_rules import may_manage_account
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
        if serializer.instance.pk!=self.request.user.pk and not may_manage_account(self.request.user,serializer.instance):
            raise PermissionDenied('Only a superuser can change an administrator account.')
        serializer.save()

    def perform_destroy(self,instance):
        if instance.pk==self.request.user.pk:
            raise PermissionDenied('You cannot delete your own account.')
        if not may_manage_account(self.request.user,instance):
            raise PermissionDenied('Only a superuser can delete an administrator account.')
        instance.delete()


class UserRoleViewSet(viewsets.ModelViewSet):
    """ViewSet for user roles."""
    queryset = UserRole.objects.order_by('pk')
    serializer_class = UserRoleSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        permissions=[IsAuthenticated] if self.action in ('list','retrieve') else [IsAuthenticated,IsAdminUser]
        return [permission() for permission in permissions]
