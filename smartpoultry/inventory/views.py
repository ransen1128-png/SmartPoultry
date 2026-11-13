from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated
from notifications.utils import create_activity_notification
from .models import Inventory, InventoryDistribution, FeedType
from .serializers import InventoryDistributionSerializer, InventorySerializer, FeedTypeSerializer
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.core.exceptions import ValidationError as ModelError


class InventoryViewSet(viewsets.ModelViewSet):
    """ViewSet for managing inventory."""
    serializer_class = InventorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Inventory.objects.filter(user=self.request.user)

    def perform_destroy(self,instance):
        if instance.distributions.exists():raise ValidationError('Items with distribution history are retained for the audit. Reverse a mistaken distribution instead.')
        instance.delete()

    def perform_update(self,serializer):
        from django.db import transaction
        with transaction.atomic():
            serializer.instance=Inventory.objects.select_for_update().get(pk=serializer.instance.pk,user=self.request.user)
            serializer.validate(dict(serializer.validated_data))
            serializer.save()

    def perform_create(self, serializer):
        item = serializer.save(user=self.request.user)
        create_activity_notification(
            self.request.user,
            f"Successfully added {item.name} to feed and inventory",
            f"{item.quantity} {item.unit} of {item.get_item_type_display().lower()} inventory was added.",
            item,
        )


class FeedTypeViewSet(viewsets.ModelViewSet):
    """ViewSet for feed types."""
    queryset = FeedType.objects.all()
    serializer_class = FeedTypeSerializer
    permission_classes = [IsAuthenticated]


class InventoryDistributionViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = InventoryDistributionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = InventoryDistribution.objects.select_related('inventory', 'branch','expense','flock').filter(user=self.request.user)
        inventory_id = self.request.query_params.get('inventory')
        if inventory_id and inventory_id.isdigit():
            queryset = queryset.filter(inventory_id=inventory_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True,methods=['post'])
    def reverse(self,request,pk=None):
        distribution=self.get_object()
        reason=request.data.get('reason','')
        if not isinstance(reason,str): raise ValidationError({'reason':'Enter a reason.'})
        try: result=distribution.reverse(request.user,reason)
        except ModelError as error: raise ValidationError(error.message_dict if hasattr(error,'message_dict') else error.messages)
        return Response(self.get_serializer(result).data)
