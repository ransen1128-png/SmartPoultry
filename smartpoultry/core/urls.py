"""
URL configuration for SMARTPOULTRY project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('__health/', views.health_check, name='health_check'),
    path('', views.index, name='index'),
    path('login/', views.index, name='login'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('register/', views.register, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('admin/', admin.site.urls),
    path('api/accounts/', include('accounts.urls')),
    path('api/flocks/', include('flocks.urls')),
    path('api/inventory/', include('inventory.urls')),
    path('api/revenue/', include('revenue.urls')),
    path('api/expenses/', include('expenses.urls')),
    path('api/analytics/', include('analytics.urls')),
    path('api/reports/', include('reports.urls')),
    path('api/production/', include('production.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    path('settings/', views.settings_view, name='settings'),
    path('feedback/', views.feedback_view, name='feedback'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-dashboard/users/<int:user_id>/toggle/', views.admin_toggle_user, name='admin_toggle_user'),
    path('admin-dashboard/users/<int:user_id>/delete/', views.admin_delete_user, name='admin_delete_user'),
    path('admin-dashboard/users/<int:user_id>/reset-password/', views.admin_reset_user_password, name='admin_reset_user_password'),
    path('admin-dashboard/feedback/', views.admin_feedback, name='admin_feedback'),
    path('admin-dashboard/feedback/<int:feedback_id>/', views.admin_feedback_detail, name='admin_feedback_detail'),
    path('admin-dashboard/feedback/<int:feedback_id>/update/', views.admin_update_feedback, name='admin_update_feedback'),
    path('admin-dashboard/feedback/<int:feedback_id>/delete/', views.admin_delete_feedback, name='admin_delete_feedback'),
    path('flocks/', views.flocks, name='flocks'),
    path('inventory/', views.inventory_view, name='inventory'),
    path('revenue/', views.revenue_view, name='revenue'),
    path('expenses/', views.expenses_view, name='expenses'),
    path('analytics/', views.analytics_view, name='analytics'),
    path('rooster-age-estimator/', views.rooster_age_estimator_view, name='rooster_age_estimator'),
    path('reports/', views.reports_view, name='reports'),
    path('production-records/', views.production_records_view, name='production_records'),
    path('production-records/add/', views.production_record_create, name='production_record_create'),
    path('production-records/<int:record_id>/edit/', views.production_record_update, name='production_record_update'),
    path('production-records/<int:record_id>/delete/', views.production_record_delete, name='production_record_delete'),
    path('mortality-records/', views.mortality_records_view, name='mortality_records'),
    path('mortality-records/add/', views.mortality_record_create, name='mortality_record_create'),
    path('mortality-records/<int:record_id>/edit/', views.mortality_record_update, name='mortality_record_update'),
    path('mortality-records/<int:record_id>/delete/', views.mortality_record_delete, name='mortality_record_delete'),
    path('forecasting/', views.forecasting_view, name='forecasting'),
    path('scenario-analysis/', views.scenario_analysis_view, name='scenario_analysis'),
    path('notifications/', views.notifications_page, name='notifications_page'),
    path('farm/branches/', views.farm_branches, name='farm_branches'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
