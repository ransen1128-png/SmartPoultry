from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BreedInformationViewSet, MortalityRecordViewSet, ProductionRecordViewSet

router = DefaultRouter()
router.register(r'records', ProductionRecordViewSet, basename='production')
router.register(r'mortality', MortalityRecordViewSet, basename='mortality')
router.register(r'breeds', BreedInformationViewSet, basename='breed')

urlpatterns = [
    path('', include(router.urls)),
]
