from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from notifications.utils import create_activity_notification
from .models import Inventory, InventoryDistribution, FeedType
from .serializers import InventoryDistributionSerializer, InventorySerializer, FeedTypeSerializer
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.core.exceptions import ValidationError as ModelError
from core.input_rules import is_record_id
from core.idempotency import IdempotentCreateMixin, idempotent


class InventoryViewSet(viewsets.ModelViewSet):
    """ViewSet for managing inventory."""
    serializer_class = InventorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Inventory.objects.filter(user=self.request.user)

    def perform_destroy(self,instance):
        if instance.quantity<=0 or instance.distributions.exists():raise ValidationError('Depleted items and items with distribution history are retained in History. Reverse a mistaken distribution instead.')
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
    """Feed types shared by every account: owners read them, administrators maintain them."""
    queryset = FeedType.objects.order_by('pk')
    serializer_class = FeedTypeSerializer

    def get_permissions(self):
        return [IsAuthenticated()] if self.action in ('list', 'retrieve') else [IsAdminUser()]


class InventoryUsageViewSet(IdempotentCreateMixin, mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    from .serializers import InventoryUsageSerializer
    serializer_class=InventoryUsageSerializer
    permission_classes=[IsAuthenticated]

    def get_queryset(self):
        from .models import InventoryUsage
        return InventoryUsage.objects.filter(user=self.request.user).select_related('distribution__inventory','distribution__branch')

    def perform_create(self,serializer):serializer.save(user=self.request.user)

    @action(detail=True,methods=['post'])
    @idempotent
    def reverse(self,request,pk=None):
        reason=request.data.get('reason','')
        if not isinstance(reason,str):raise ValidationError({'reason':'Enter a reversal reason.'})
        try:row=self.get_object().reverse(request.user,reason)
        except ModelError as error:raise ValidationError(error.message_dict)
        return Response(self.get_serializer(row).data)


class InventoryDistributionViewSet(IdempotentCreateMixin, mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = InventoryDistributionSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False,methods=['get'],url_path='branch-stock')
    def branch_stock(self,request):
        from django.db.models import Sum, Q
        from decimal import Decimal
        lots=self.get_queryset().filter(reversed_at__isnull=True).annotate(
            used=Sum('usages__quantity',filter=Q(usages__voided_at__isnull=True)))
        return Response([{'id':lot.pk,'branch':lot.branch_id,'branch_name':lot.branch.name,
            'item_name':lot.inventory.name,'date':lot.date,'received':str(lot.quantity),
            'used':str(lot.used or Decimal('0')),'remaining':str(lot.quantity-(lot.used or Decimal('0'))),
            'unit':lot.unit_snapshot,'package_size':lot.package_size_snapshot,'content_unit':lot.content_unit_snapshot,
            'active':lot.branch.status=='active'} for lot in lots])

    def create(self,request,*args,**kwargs):
        from django.db import transaction
        # Include response serialization in the same transaction as stock and cost.
        with transaction.atomic():
            return super().create(request,*args,**kwargs)

    def get_queryset(self):
        queryset = InventoryDistribution.objects.select_related('inventory', 'branch','expense','flock').filter(user=self.request.user)
        inventory_id = self.request.query_params.get('inventory')
        if is_record_id(inventory_id):
            queryset = queryset.filter(inventory_id=inventory_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True,methods=['post'])
    @idempotent
    def reverse(self,request,pk=None):
        distribution=self.get_object()
        reason=request.data.get('reason','')
        if not isinstance(reason,str): raise ValidationError({'reason':'Enter a reason.'})
        try: result=distribution.reverse(request.user,reason)
        except ModelError as error: raise ValidationError(error.message_dict if hasattr(error,'message_dict') else error.messages)
        return Response(self.get_serializer(result).data)
