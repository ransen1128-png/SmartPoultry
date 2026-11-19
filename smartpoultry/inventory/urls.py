from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import InventoryDistributionViewSet, InventoryViewSet, FeedTypeViewSet, InventoryUsageViewSet

router = DefaultRouter()
router.register(r'items', InventoryViewSet, basename='inventory')
router.register(r'distributions', InventoryDistributionViewSet, basename='inventory-distribution')
router.register(r'usage', InventoryUsageViewSet, basename='inventory-usage')
router.register(r'feed-types', FeedTypeViewSet, basename='feed_type')

urlpatterns = [
    path('', include(router.urls)),
]
