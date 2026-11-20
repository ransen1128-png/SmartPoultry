"""
URL configuration for SMARTPOULTRY project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import views
from .measurement_review import review_spur
from .spur_cache_service import service as spur_cache_service, connection_page
from . import business_views
from django.contrib.auth.views import PasswordResetCompleteView
from .password_reset import RequestPasswordResetView, ConfirmPasswordResetView, ResetRequestDoneView
from . import admin_notifications
from . import recovery_questions

urlpatterns = [
    path('revenue/<int:sale_id>/receipt/',business_views.sales_receipt,name='sales_receipt'),
    path('change-history/',business_views.activity_history,name='activity_history'),
    path('reliability-status/',business_views.reliability_status,name='reliability_status'),
    path('__health/', views.health_check, name='health_check'),
    path('api/spur-cache/<str:action>/', spur_cache_service, name='spur_cache_service'),
    path('rooster-age-estimator/shared-cache/', connection_page, name='spur_cache_connection'),
    path('', views.index, name='index'),
    path('login/', views.index, name='login'),
    path('forgot-password/', RequestPasswordResetView.as_view(), name='forgot_password'),
    path('forgot-password/admin-help/', RequestPasswordResetView.as_view(recovery_method='admin'), name='request_admin_password_reset'),
    path('forgot-password/questions/', recovery_questions.answer_questions, name='recovery_questions'),
    path('forgot-password/new-password/', recovery_questions.change_password, name='question_password_reset'),
    path('forgot-password/sent/', ResetRequestDoneView.as_view(), name='password_reset_done'),
    path('reset-password/<uidb64>/<token>/', ConfirmPasswordResetView.as_view(), name='password_reset_confirm'),
    path('reset-password/complete/', PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'), name='password_reset_complete'),
    path('register/', views.register, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('signed-out/', views.logout_complete, name='logout_complete'),
    path('session-status/', views.session_status, name='session_status'),
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
    path('admin-dashboard/notifications/', admin_notifications.poll, name='admin_notifications_poll'),
    path('admin-dashboard/password-requests/', admin_notifications.requests_page, name='admin_password_reset_requests'),
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
    path('rooster-age-estimator/photos/<int:estimate_id>/', views.rooster_estimate_photo, name='rooster_estimate_photo'),
    path('rooster-age-estimator/<int:estimate_id>/review-spur/', review_spur, name='review_spur_measurement'),
    path('reports/', views.reports_view, name='reports'),
    path('production-records/', views.production_records_view, name='production_records'),
    path('production-records/add/', views.production_record_create, name='production_record_create'),
    path('production-records/<int:record_id>/apply-birds/', views.production_apply_birds, name='production_apply_birds'),
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
