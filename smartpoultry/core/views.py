import os
from datetime import date, timedelta

from django.conf import settings
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponseForbidden, JsonResponse
from django.utils import timezone
from django.utils.text import capfirst
from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError
from notifications.utils import create_activity_notification
from .forms import MortalityRecordForm, ProductionRecordForm
from .models import Feedback, RoosterAgeEstimate, Farm, Branch

User = get_user_model()
DEPLOY_MARKER = 'smartpoultry-health-2026-07-04-01'


def health_check(request):
    """Lightweight production diagnostic that avoids templates and database queries."""
    database = settings.DATABASES['default']
    static_dirs = [str(path) for path in getattr(settings, 'STATICFILES_DIRS', [])]
    static_sources = {
        'source_logo_exists': any((path / 'images' / 'smartpoultry_logo.svg').exists() for path in getattr(settings, 'STATICFILES_DIRS', [])),
        'collected_logo_exists': (settings.STATIC_ROOT / 'images' / 'smartpoultry_logo.svg').exists(),
    }
    return JsonResponse({
        'ok': True,
        'marker': DEPLOY_MARKER,
        'render': bool(os.getenv('RENDER') or os.getenv('RENDER_EXTERNAL_HOSTNAME')),
        'render_hostname': os.getenv('RENDER_EXTERNAL_HOSTNAME', ''),
        'debug': settings.DEBUG,
        'allowed_hosts': settings.ALLOWED_HOSTS,
        'database_engine': database.get('ENGINE', ''),
        'database_host': database.get('HOST', ''),
        'database_name': str(database.get('NAME', '')),
        'static_url': settings.STATIC_URL,
        'static_root': str(settings.STATIC_ROOT),
        'static_dirs': static_dirs,
        'staticfiles_storage': getattr(settings, 'STATICFILES_STORAGE', ''),
        'whitenoise_use_finders': getattr(settings, 'WHITENOISE_USE_FINDERS', None),
        **static_sources,
    })


def is_admin_user(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def admin_required(view_func):
    """Allow access only to staff or superuser accounts."""
    @login_required(login_url='login')
    def wrapper(request, *args, **kwargs):
        if is_admin_user(request.user):
            return view_func(request, *args, **kwargs)
        return HttpResponseForbidden('You do not have permission to access this page.')
    return wrapper


def index(request):
    """Login page view."""
    if request.user.is_authenticated:
        if is_admin_user(request.user):
            return redirect('admin_dashboard')
        return redirect('dashboard')

    error = None
    if request.method == 'POST':
        identifier = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        if identifier and password:
            username = identifier
            if '@' in identifier:
                try:
                    user_obj = User.objects.get(email__iexact=identifier)
                    username = user_obj.username
                except User.DoesNotExist:
                    username = identifier
            user = authenticate(request, username=username, password=password)
            if user is not None and user.is_active:
                login(request, user)
                if is_admin_user(user):
                    return redirect('admin_dashboard')
                return redirect('dashboard')
            error = 'Invalid login credentials. Please try again.'
        else:
            error = 'Email and password are required.'
    return render(request, 'index.html', {'error': error})


def register(request):
    """User registration page view."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        if not username or not email or not password or not password2:
            error = 'Please fill out all fields.'
        elif password != password2:
            error = 'Passwords do not match.'
        elif User.objects.filter(username=username).exists():
            error = 'Username already taken.'
        elif User.objects.filter(email=email).exists():
            error = 'Email already registered.'
        else:
            user = User.objects.create_user(username=username, email=email, password=password)
            user.is_active = True
            user.save()
            login(request, user)
            return redirect('dashboard')
    return render(request, 'register.html', {'error': error})


def forgot_password(request):
    """Public password reset page for users who forgot their password."""
    if request.user.is_authenticated:
        if is_admin_user(request.user):
            return redirect('admin_dashboard')
        return redirect('dashboard')

    error = None
    success = None
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if not email or not new_password or not confirm_password:
            error = 'Please fill out all fields.'
        elif new_password != confirm_password:
            error = 'Passwords do not match.'
        else:
            try:
                user = User.objects.get(email__iexact=email)
                validate_password(new_password, user)
            except User.DoesNotExist:
                error = 'No account was found with that email address.'
            except ValidationError as exc:
                error = ' '.join(exc.messages)
            else:
                user.set_password(new_password)
                user.save()
                success = 'Password reset successfully. You can now log in with your new password.'

    return render(request, 'forgot_password.html', {'error': error, 'success': success})


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required(login_url='login')
def dashboard(request):
    """Dashboard view with overview."""
    if is_admin_user(request.user):
        return redirect('admin_dashboard')

    from expenses.models import Expense
    from flocks.models import Flock
    from inventory.models import Inventory
    from production.models import MortalityRecord, ProductionRecord
    from revenue.models import Revenue

    today = timezone.localdate()
    current_month_start = today.replace(day=1)
    if current_month_start.month == 1:
        previous_month_start = current_month_start.replace(year=current_month_start.year - 1, month=12)
    else:
        previous_month_start = current_month_start.replace(month=current_month_start.month - 1)

    def decimal_sum(queryset, field):
        return queryset.aggregate(total=Sum(field))['total'] or 0

    def percent_change(current, previous):
        if not previous:
            return None
        return round(((current - previous) / previous) * 100, 1)

    current_revenue = decimal_sum(Revenue.objects.filter(user=request.user, date__gte=current_month_start), 'total_amount')
    previous_revenue = decimal_sum(
        Revenue.objects.filter(user=request.user, date__gte=previous_month_start, date__lt=current_month_start),
        'total_amount',
    )
    current_expenses = decimal_sum(Expense.objects.filter(user=request.user, date__gte=current_month_start), 'amount')
    previous_expenses = decimal_sum(
        Expense.objects.filter(user=request.user, date__gte=previous_month_start, date__lt=current_month_start),
        'amount',
    )
    current_profit = current_revenue - current_expenses
    previous_profit = previous_revenue - previous_expenses
    feed_cost = decimal_sum(
        Expense.objects.filter(user=request.user, date__gte=current_month_start, expense_type='feed'),
        'amount',
    )
    production_total = decimal_sum(
        ProductionRecord.objects.filter(user=request.user, date__gte=current_month_start, product_type='eggs'),
        'quantity',
    )
    mortality_total = MortalityRecord.objects.filter(user=request.user, date__gte=current_month_start).aggregate(
        total=Sum('quantity')
    )['total'] or 0
    total_birds = Flock.objects.filter(user=request.user, status='active').aggregate(total=Sum('quantity'))['total'] or 0
    active_flocks = Flock.objects.filter(user=request.user, status='active').count()
    mortality_rate = round((mortality_total / total_birds) * 100, 2) if total_birds else 0
    feed_stock = decimal_sum(Inventory.objects.filter(user=request.user, item_type='feed'), 'quantity')
    feed_expense_share = round((feed_cost / current_expenses) * 100, 1) if current_expenses else 0

    trend_start = current_month_start
    for _ in range(5):
        if trend_start.month == 1:
            trend_start = trend_start.replace(year=trend_start.year - 1, month=12)
        else:
            trend_start = trend_start.replace(month=trend_start.month - 1)

    def month_key(value):
        return value.date() if hasattr(value, 'date') else value

    revenue_by_month = {
        month_key(item['month']): item['total'] or 0
        for item in Revenue.objects.filter(user=request.user, date__gte=trend_start)
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(total=Sum('total_amount'))
    }
    expenses_by_month = {
        month_key(item['month']): item['total'] or 0
        for item in Expense.objects.filter(user=request.user, date__gte=trend_start)
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(total=Sum('amount'))
    }
    feed_by_month = {
        month_key(item['month']): item['total'] or 0
        for item in Expense.objects.filter(user=request.user, date__gte=trend_start, expense_type='feed')
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(total=Sum('amount'))
    }

    chart_months = []
    month_cursor = trend_start
    for _ in range(6):
        chart_months.append(month_cursor)
        if month_cursor.month == 12:
            month_cursor = month_cursor.replace(year=month_cursor.year + 1, month=1)
        else:
            month_cursor = month_cursor.replace(month=month_cursor.month + 1)

    revenue_values = [float(revenue_by_month.get(month, 0)) for month in chart_months]
    expense_values = [float(expenses_by_month.get(month, 0)) for month in chart_months]
    feed_values = [float(feed_by_month.get(month, 0)) for month in chart_months]
    profit_values = [revenue_values[index] - expense_values[index] for index in range(len(chart_months))]

    latest_notification = 'No recent notifications'
    try:
        from notifications.models import Notification
        notification = Notification.objects.filter(user=request.user).first()
        if notification:
            latest_notification = notification.title
    except Exception:
        pass

    context = {
        'date_range_label': f'{current_month_start:%b} 1 - {today:%b} {today.day}, {today.year}',
        'metrics': {
            'revenue': current_revenue,
            'revenue_change': percent_change(current_revenue, previous_revenue),
            'expenses': current_expenses,
            'expenses_change': percent_change(current_expenses, previous_expenses),
            'profit': current_profit,
            'profit_change': percent_change(current_profit, previous_profit),
            'cash_flow': current_profit,
            'feed_cost': feed_cost,
            'feed_expense_share': feed_expense_share,
            'mortality_rate': mortality_rate,
            'total_birds': total_birds,
            'active_flocks': active_flocks,
            'production_total': production_total,
            'feed_stock': feed_stock,
            'latest_notification': latest_notification,
        },
        'chart_data': {
            'labels': [capfirst(month.strftime('%b')) for month in chart_months],
            'revenue': revenue_values,
            'expenses': expense_values,
            'profit': profit_values,
            'feed': feed_values,
        },
    }
    return render(request, 'dashboard.html', context)


@login_required(login_url='login')
def profile_view(request):
    """Manage the signed-in user's profile."""
    if request.method == 'POST':
        user = request.user
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()

        if not username or not email:
            messages.error(request, 'Username and email are required.')
        elif User.objects.exclude(pk=user.pk).filter(username=username).exists():
            messages.error(request, 'That username is already taken.')
        elif User.objects.exclude(pk=user.pk).filter(email=email).exists():
            messages.error(request, 'That email is already registered.')
        else:
            user.username = username
            user.email = email
            user.first_name = request.POST.get('first_name', '').strip()
            user.last_name = request.POST.get('last_name', '').strip()
            user.phone = request.POST.get('phone', '').strip()
            user.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('profile')

    return render(request, 'profile.html')


@login_required(login_url='login')
def settings_view(request):
    """Account settings for password and notification preferences."""
    preference = None
    try:
        from notifications.models import NotificationPreference
        preference, _ = NotificationPreference.objects.get_or_create(user=request.user)
    except Exception:
        preference = None

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'notifications' and preference:
            preference.email_alerts = request.POST.get('email_alerts') == 'on'
            preference.email_notifications = request.POST.get('email_notifications') == 'on'
            preference.in_app_notifications = request.POST.get('in_app_notifications') == 'on'
            preference.push_notifications = request.POST.get('push_notifications') == 'on'
            preference.save()
            messages.success(request, 'Notification settings updated.')
            return redirect('settings')

        if action == 'password':
            current_password = request.POST.get('current_password', '')
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')

            if not request.user.check_password(current_password):
                messages.error(request, 'Current password is incorrect.')
            elif new_password != confirm_password:
                messages.error(request, 'New passwords do not match.')
            else:
                try:
                    validate_password(new_password, request.user)
                except ValidationError as exc:
                    messages.error(request, ' '.join(exc.messages))
                else:
                    request.user.set_password(new_password)
                    request.user.save()
                    update_session_auth_hash(request, request.user)
                    messages.success(request, 'Password updated successfully.')
                    return redirect('settings')

    return render(request, 'settings.html', {'preference': preference})


@login_required(login_url='login')
def feedback_view(request):
    """Allow users to submit feedback or reviews."""
    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        rating = request.POST.get('rating', '5')

        if not subject or not message:
            messages.error(request, 'Subject and message are required.')
        else:
            try:
                rating = max(1, min(5, int(rating)))
            except ValueError:
                rating = 5
            Feedback.objects.create(
                user=request.user,
                subject=subject,
                message=message,
                rating=rating,
            )
            messages.success(request, 'Thank you. Your feedback was submitted.')
            return redirect('feedback')

    feedback_items = Feedback.objects.filter(user=request.user)
    return render(request, 'feedback.html', {'feedback_items': feedback_items})


@login_required(login_url='login')
def farm_branches(request):
    """List and create branches for the user's farm."""
    farm = None
    try:
        farm = request.user.owned_farm
    except Farm.DoesNotExist:
        messages.info(request, 'You need a farm profile before managing branches.')

    if request.method == 'POST':
        if farm is None:
            farm_name = request.POST.get('farm_name', '').strip()
            farm_location = request.POST.get('farm_location', '').strip()
            established_date = request.POST.get('established_date', '').strip()
            contact_email = request.POST.get('contact_email', '').strip()
            contact_phone = request.POST.get('contact_phone', '').strip()

            if not farm_name or not farm_location or not established_date or not contact_email or not contact_phone:
                messages.error(request, 'All farm profile fields are required.')
            else:
                try:
                    farm = Farm.objects.create(
                        owner=request.user,
                        name=farm_name,
                        location=farm_location,
                        established_date=established_date,
                        contact_email=contact_email,
                        contact_phone=contact_phone,
                    )
                    messages.success(request, 'Farm profile created successfully. You can now add branches.')
                    return redirect('farm_branches')
                except Exception:
                    messages.error(request, 'Unable to create farm profile. Please check your input.')
        else:
            name = request.POST.get('branch_name', '').strip()
            location = request.POST.get('location', '').strip()
            address = request.POST.get('address', '').strip()
            contact_number = request.POST.get('contact_number', '').strip()
            description = request.POST.get('description', '').strip()
            status = request.POST.get('status', 'active')

            if not name:
                messages.error(request, 'Branch name is required.')
            else:
                Branch.objects.create(
                    farm=farm,
                    name=name,
                    location=location,
                    address=address,
                    contact_number=contact_number,
                    description=description,
                    status=status,
                )
                messages.success(request, 'Branch added successfully.')
                return redirect('farm_branches')

    branches = farm.branches.all() if farm is not None else []
    return render(request, 'farm_branches.html', {'farm': farm, 'branches': branches})


@admin_required
def admin_dashboard(request):
    """Admin dashboard for user accounts and feedback management."""
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    users = User.objects.select_related('farm').order_by('id')
    if query:
        users = users.filter(
            Q(username__icontains=query) |
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(farm__name__icontains=query)
        )
    if status == 'active':
        users = users.filter(is_active=True, is_active_user=True)
    elif status == 'inactive':
        users = users.filter(Q(is_active=False) | Q(is_active_user=False))

    feedback_items = Feedback.objects.select_related('user').all()[:10]
    stats = {
        'total_users': User.objects.count(),
        'active_users': User.objects.filter(is_active=True, is_active_user=True).count(),
        'inactive_users': User.objects.filter(Q(is_active=False) | Q(is_active_user=False)).count(),
        'new_feedback': Feedback.objects.filter(status='new').count(),
        'new_users_today': User.objects.filter(date_joined__date=timezone.localdate()).count(),
    }
    feedback_status_counts = Feedback.objects.values('status').annotate(total=Count('id'))

    return render(request, 'admin_dashboard.html', {
        'managed_users': users,
        'feedback_items': feedback_items,
        'feedback_status_counts': feedback_status_counts,
        'stats': stats,
        'query': query,
        'status': status,
    })


@admin_required
def admin_toggle_user(request, user_id):
    if request.method != 'POST':
        return redirect('admin_dashboard')

    target_user = get_object_or_404(User, pk=user_id)
    if target_user.pk == request.user.pk:
        messages.error(request, 'You cannot deactivate your own account.')
    else:
        activate = request.POST.get('action') == 'activate'
        target_user.is_active = activate
        target_user.is_active_user = activate
        target_user.save()
        messages.success(request, f"{target_user.username} has been {'activated' if activate else 'deactivated'}.")
    return redirect('admin_dashboard')


@admin_required
def admin_delete_user(request, user_id):
    if request.method != 'POST':
        return redirect('admin_dashboard')

    target_user = get_object_or_404(User, pk=user_id)
    if target_user.pk == request.user.pk:
        messages.error(request, 'You cannot delete your own account.')
    elif target_user.is_superuser and not request.user.is_superuser:
        messages.error(request, 'Only a superuser can delete another superuser.')
    else:
        username = target_user.username
        target_user.delete()
        messages.success(request, f'{username} was deleted.')
    return redirect('admin_dashboard')


@admin_required
def admin_reset_user_password(request, user_id):
    target_user = get_object_or_404(User, pk=user_id)
    if request.method == 'POST':
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if new_password != confirm_password:
            messages.error(request, 'Passwords do not match.')
        else:
            try:
                validate_password(new_password, target_user)
            except ValidationError as exc:
                messages.error(request, ' '.join(exc.messages))
            else:
                target_user.set_password(new_password)
                target_user.save()
                messages.success(request, f'Password reset for {target_user.username}.')
                return redirect('admin_dashboard')

    return render(request, 'admin_reset_password.html', {'target_user': target_user})


@admin_required
def admin_feedback(request):
    feedback_items = Feedback.objects.select_related('user').all()
    status = request.GET.get('status', '').strip()
    if status:
        feedback_items = feedback_items.filter(status=status)
    return render(request, 'admin_feedback.html', {
        'feedback_items': feedback_items,
        'status': status,
        'status_choices': Feedback.STATUS_CHOICES,
    })


@admin_required
def admin_feedback_detail(request, feedback_id):
    """Read one feedback item and respond to it."""
    feedback = get_object_or_404(Feedback.objects.select_related('user'), pk=feedback_id)
    if request.method == 'POST':
        feedback.status = request.POST.get('status', feedback.status)
        feedback.admin_response = request.POST.get('admin_response', '').strip()
        feedback.save()
        messages.success(request, 'Feedback response saved.')
        return redirect('admin_feedback_detail', feedback_id=feedback.id)

    return render(request, 'admin_feedback_detail.html', {
        'feedback': feedback,
        'status_choices': Feedback.STATUS_CHOICES,
    })


@admin_required
def admin_update_feedback(request, feedback_id):
    if request.method != 'POST':
        return redirect('admin_feedback')

    feedback = get_object_or_404(Feedback, pk=feedback_id)
    feedback.status = request.POST.get('status', feedback.status)
    feedback.admin_response = request.POST.get('admin_response', '').strip()
    feedback.save()
    messages.success(request, 'Feedback updated.')
    return redirect('admin_feedback')


@admin_required
def admin_delete_feedback(request, feedback_id):
    if request.method == 'POST':
        feedback = get_object_or_404(Feedback, pk=feedback_id)
        feedback.delete()
        messages.success(request, 'Feedback deleted.')
    return redirect('admin_feedback')


@login_required(login_url='login')
def flocks(request):
    """Flocks management view."""
    branches = []
    try:
        branches = list(request.user.owned_farm.branches.all())
    except Farm.DoesNotExist:
        pass
    return render(request, 'flocks.html', {'branches': branches})


@login_required(login_url='login')
def inventory_view(request):
    """Inventory management view."""
    return render(request, 'inventory.html')


@login_required(login_url='login')
def revenue_view(request):
    """Revenue tracking view."""
    branches = []
    try:
        branches = list(request.user.owned_farm.branches.all())
    except Farm.DoesNotExist:
        pass
    return render(request, 'revenue.html', {'branches': branches})


@login_required(login_url='login')
def expenses_view(request):
    """Expenses tracking view."""
    branches = []
    try:
        branches = list(request.user.owned_farm.branches.all())
    except Farm.DoesNotExist:
        pass
    return render(request, 'expenses.html', {'branches': branches})


@login_required(login_url='login')
def analytics_view(request):
    """Analytics and predictions view."""
    from analytics.models import Prediction
    from expenses.models import Expense
    from production.models import ProductionRecord
    from revenue.models import Revenue

    today = timezone.localdate()
    current_month_start = today.replace(day=1)

    def add_months(value, months):
        month_index = value.month - 1 + months
        year = value.year + month_index // 12
        month = month_index % 12 + 1
        return value.replace(year=year, month=month, day=1)

    def decimal_sum(queryset, field):
        return queryset.aggregate(total=Sum(field))['total'] or 0

    def month_key(value):
        return value.date() if hasattr(value, 'date') else value

    def trend_forecast(values, periods):
        numeric_values = [float(value) for value in values if value is not None]
        if not numeric_values:
            return [0 for _ in range(periods)]
        if len(numeric_values) == 1:
            return [round(numeric_values[0], 2) for _ in range(periods)]

        recent_window = numeric_values[-3:] if len(numeric_values) >= 3 else numeric_values
        baseline = sum(recent_window) / len(recent_window)
        slope = (numeric_values[-1] - numeric_values[0]) / max(len(numeric_values) - 1, 1)
        return [round(max(0, baseline + slope * step), 2) for step in range(1, periods + 1)]

    history_start = add_months(current_month_start, -5)
    future_months = [add_months(current_month_start, offset) for offset in range(1, 7)]
    history_months = [add_months(history_start, offset) for offset in range(6)]

    revenue_by_month = {
        month_key(item['month']): item['total'] or 0
        for item in Revenue.objects.filter(user=request.user, date__gte=history_start)
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(total=Sum('total_amount'))
    }
    expense_by_month = {
        month_key(item['month']): item['total'] or 0
        for item in Expense.objects.filter(user=request.user, date__gte=history_start)
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(total=Sum('amount'))
    }

    actual_revenue = [
        float(revenue_by_month[month]) if month in revenue_by_month else None
        for month in history_months
    ]
    actual_expenses = [float(expense_by_month.get(month, 0)) for month in history_months]
    revenue_forecast_source = [
        float(revenue_by_month[month])
        for month in history_months
        if month in revenue_by_month
    ]
    actual_profit = [
        round((actual_revenue[index] or 0) - actual_expenses[index], 2)
        for index in range(len(history_months))
    ]

    predicted_revenue = trend_forecast(revenue_forecast_source, 6)
    predicted_expenses = trend_forecast(actual_expenses, 6)
    predicted_profit = [
        round(predicted_revenue[index] - predicted_expenses[index], 2)
        for index in range(len(future_months))
    ]

    week_starts = [today - timedelta(days=today.weekday() + (5 - index) * 7) for index in range(6)]
    production_by_week = []
    for week_start in week_starts:
        week_end = week_start + timedelta(days=7)
        production_by_week.append(float(decimal_sum(
            ProductionRecord.objects.filter(
                user=request.user,
                product_type='eggs',
                date__gte=week_start,
                date__lt=week_end,
            ),
            'quantity',
        )))
    predicted_production = trend_forecast(production_by_week, 6)

    method = 'SQLite recent trend forecast'
    for index, forecast_month in enumerate(future_months):
        Prediction.objects.update_or_create(
            user=request.user,
            prediction_type='profit',
            forecast_date=forecast_month,
            defaults={
                'predicted_value': predicted_profit[index],
                'method': method,
                'accuracy_percentage': 0,
            },
        )
        Prediction.objects.update_or_create(
            user=request.user,
            prediction_type='eggs',
            forecast_date=forecast_month,
            defaults={
                'predicted_value': predicted_production[index],
                'method': method,
                'accuracy_percentage': 0,
            },
        )

    latest_predictions = Prediction.objects.filter(
        user=request.user,
        prediction_type__in=['profit', 'eggs'],
        forecast_date__in=future_months,
    ).order_by('forecast_date', 'prediction_type')

    all_months = history_months + future_months
    chart_data = {
        'actualVsPredicted': {
            'labels': [capfirst(month.strftime('%b %Y')) for month in all_months],
            'actualRevenue': actual_revenue + [None for _ in future_months],
            'predictedRevenue': [None for _ in history_months] + predicted_revenue,
        },
        'profit': {
            'labels': [capfirst(month.strftime('%b %Y')) for month in future_months],
            'values': predicted_profit,
        },
        'production': {
            'labels': [f'Week {index}' for index in range(1, 7)],
            'actual': production_by_week,
            'predicted': predicted_production,
        },
    }

    return render(request, 'analytics.html', {
        'chart_data': chart_data,
        'latest_predictions': latest_predictions,
        'prediction_method': method,
        'last_updated': timezone.now(),
    })


def analyze_rooster_photo(photo):
    try:
        photo.seek(0)
        with Image.open(photo) as image:
            image = image.convert('L')
            width, height = image.size
            resized = image.resize((min(width, 512), max(1, int(height * min(width, 512) / width))))
            stat = ImageStat.Stat(resized)
            brightness = stat.mean[0]
            contrast = stat.stddev[0]
            edge_stat = ImageStat.Stat(resized.filter(ImageFilter.FIND_EDGES))
            sharpness = edge_stat.stddev[0]
    except (UnidentifiedImageError, OSError, ValueError, ZeroDivisionError):
        photo.seek(0)
        return {
            'quality': 'unreadable',
            'summary': 'The uploaded file could not be analyzed as a readable image.',
            'penalty': 2,
        }
    finally:
        photo.seek(0)

    quality_flags = []
    if width < 600 or height < 450:
        quality_flags.append('low resolution')
    if brightness < 45:
        quality_flags.append('too dark')
    elif brightness > 220:
        quality_flags.append('too bright')
    if contrast < 22:
        quality_flags.append('low contrast')
    if sharpness < 8:
        quality_flags.append('soft or blurry')

    if not quality_flags:
        return {
            'quality': 'good',
            'summary': f'Photo quality supports visual assessment ({width}x{height}, adequate brightness and detail).',
            'penalty': 0,
        }

    penalty = 2 if len(quality_flags) >= 3 else 1
    return {
        'quality': 'limited',
        'summary': f'Photo may limit accuracy ({width}x{height}; {", ".join(quality_flags)}).',
        'penalty': penalty,
    }


def adjust_confidence(confidence, photo_analysis):
    levels = ['Low', 'Medium', 'Medium-High', 'High']
    if not photo_analysis:
        return confidence
    penalty = photo_analysis.get('penalty', 0)
    if penalty <= 0:
        return confidence
    try:
        index = levels.index(confidence)
    except ValueError:
        return 'Low'
    return levels[max(0, index - penalty)]


def score_secondary_clues(secondary_clues):
    clues = secondary_clues.lower()
    younger_terms = ['small comb', 'pale comb', 'juvenile', 'young', 'small body', 'soft legs', 'smooth legs']
    mature_terms = ['large comb', 'red comb', 'bright comb', 'full body', 'large body', 'adult feathers', 'sickle feathers']
    older_terms = ['rough legs', 'coarse legs', 'thick legs', 'worn scales', 'heavy body']

    adjustment = 0
    matched = []
    if any(term in clues for term in younger_terms):
        adjustment -= 1
        matched.append('younger secondary features')
    if any(term in clues for term in mature_terms):
        adjustment += 1
        matched.append('mature secondary features')
    if any(term in clues for term in older_terms):
        adjustment += 1
        matched.append('older leg/body features')
    return adjustment, matched


def estimate_rooster_age_from_spurs(visibility, length, thickness, point_shape, curvature, secondary_clues, photo_analysis=None):
    if visibility != 'clear':
        limitation = 'Spurs are hidden, cropped, blurry, or too small in the photo.'
        if photo_analysis:
            limitation = f"{limitation} {photo_analysis['summary']}"
        return {
            'age_range': 'insufficient spur visibility for reliable age estimate',
            'reasoning': (
                'The spurs are not visible enough to evaluate length, thickness, point shape, and curvature '
                'with confidence, so a spur-based age range would be unreliable.'
            ),
            'confidence': 'Low',
            'limitations': limitation,
        }

    score = 0
    score += {'none': 0, 'buds': 1, 'short': 2, 'medium': 3, 'long': 4}.get(length, 0)
    score += {'thin': 0, 'moderate': 1, 'thick': 2}.get(thickness, 0)
    score += {'rounded': 0, 'pointed': 1, 'worn': 2}.get(point_shape, 0)
    score += {'straight': 0, 'slight': 1, 'curved': 2}.get(curvature, 0)
    secondary_adjustment, secondary_matches = score_secondary_clues(secondary_clues)
    score = max(0, score + secondary_adjustment)

    if score <= 1:
        age_range = 'under 6 months'
        confidence = 'Medium'
        reasoning = 'Spurs are absent or only beginning as small buds, which is most consistent with a juvenile rooster.'
    elif score <= 3:
        age_range = '6 to 10 months'
        confidence = 'Medium'
        reasoning = 'Spurs appear short and lightly developed, suggesting a young rooster approaching maturity.'
    elif score <= 5:
        age_range = '10 to 18 months'
        confidence = 'Medium-High'
        reasoning = 'Spurs show clear extension with moderate thickness or a pointed tip, which commonly fits a young adult.'
    elif score <= 7:
        age_range = '18 months to 3 years'
        confidence = 'Medium-High'
        reasoning = 'Spurs are developed in length and thickness, with noticeable point or curvature, matching a mature adult.'
    else:
        age_range = '3 years or older'
        confidence = 'Medium'
        reasoning = 'Spurs are long, thick, curved, or worn, which is more typical of an older mature rooster.'

    if secondary_clues:
        reasoning = f'{reasoning} Secondary clues noted: {secondary_clues}'
        if secondary_matches:
            reasoning = f"{reasoning} These adjusted the estimate for {', '.join(secondary_matches)}."

    if photo_analysis:
        if photo_analysis.get('quality') == 'good' and confidence == 'Medium':
            confidence = 'Medium-High'
        confidence = adjust_confidence(confidence, photo_analysis)
        reasoning = f"{reasoning} Image check: {photo_analysis['summary']}"

    return {
        'age_range': age_range,
        'reasoning': reasoning,
        'confidence': confidence,
        'limitations': (
            'This estimate combines spur observations from the uploaded photo with basic image quality checks. '
            'Breed, trimming, injury, image angle, and husbandry conditions can change spur appearance.'
        ),
    }


@login_required(login_url='login')
def rooster_age_estimator_view(request):
    """Estimate rooster age ranges using user-entered spur observations from uploaded photos."""
    results = []
    visibility_labels = {
        'clear': 'Spurs clearly visible',
        'partial': 'Partially visible',
        'hidden': 'Hidden or not visible',
    }
    length_labels = {
        'none': 'none visible',
        'buds': 'small spur buds',
        'short': 'short spurs',
        'medium': 'medium spurs',
        'long': 'long spurs',
    }
    thickness_labels = {
        'thin': 'thin',
        'moderate': 'moderate',
        'thick': 'thick',
    }
    point_labels = {
        'rounded': 'rounded or blunt point',
        'pointed': 'sharp pointed tip',
        'worn': 'worn or irregular point',
    }
    curvature_labels = {
        'straight': 'straight',
        'slight': 'slightly curved',
        'curved': 'strongly curved',
    }

    if request.method == 'POST':
        photos = request.FILES.getlist('photos')
        rooster_count = len(photos)

        for index in range(rooster_count):
            def value_from_list(name, default=''):
                values = request.POST.getlist(name)
                return values[index] if index < len(values) else default

            visibility = value_from_list('spur_visibility', 'hidden')
            length = value_from_list('spur_length', 'none')
            thickness = value_from_list('spur_thickness', 'thin')
            point_shape = value_from_list('spur_point_shape', 'rounded')
            curvature = value_from_list('spur_curvature', 'straight')
            secondary_clues = value_from_list('secondary_clues', '').strip()
            photo = photos[index]
            photo_analysis = analyze_rooster_photo(photo)
            estimate = estimate_rooster_age_from_spurs(
                visibility,
                length,
                thickness,
                point_shape,
                curvature,
                secondary_clues,
                photo_analysis,
            )
            photo_name = photo.name
            spur_observations = (
                f"Visibility: {visibility_labels.get(visibility, visibility)}. "
                f"Length: {length_labels.get(length, length)}. "
                f"Thickness: {thickness_labels.get(thickness, thickness)}. "
                f"Point shape: {point_labels.get(point_shape, point_shape)}. "
                f"Curvature: {curvature_labels.get(curvature, curvature)}. "
                f"Image quality: {photo_analysis['summary']}"
            )

            record_data = {
                'user': request.user,
                'photo_name': photo_name,
                'spur_visibility': visibility,
                'spur_length': length,
                'spur_thickness': thickness,
                'spur_point_shape': point_shape,
                'spur_curvature': curvature,
                'secondary_clues': secondary_clues,
                'estimated_age_range': estimate['age_range'],
                'spur_observations': spur_observations,
                'reasoning': estimate['reasoning'],
                'confidence': estimate['confidence'],
                'limitations': estimate['limitations'],
            }
            record_data['photo'] = photo

            record = RoosterAgeEstimate.objects.create(
                **record_data
            )

            results.append({
                'number': index + 1,
                'id': record.id,
                'photo_name': photo_name,
                'estimated_age_range': estimate['age_range'],
                'spur_observations': spur_observations,
                'image_assessment': photo_analysis['summary'],
                'reasoning': estimate['reasoning'],
                'confidence': estimate['confidence'],
                'limitations': estimate['limitations'],
            })

        if results:
            messages.success(request, f"Saved {len(results)} rooster age estimate{'s' if len(results) != 1 else ''} to the database.")
        else:
            messages.error(request, 'Upload at least one rooster photo before estimating age.')

    saved_estimates = RoosterAgeEstimate.objects.filter(user=request.user).exclude(photo='')[:20]
    return render(request, 'rooster_age_estimator.html', {
        'results': results,
        'saved_estimates': saved_estimates,
    })


@login_required(login_url='login')
def reports_view(request):
    """Reports view."""
    return render(request, 'reports.html')


@login_required(login_url='login')
def production_records_view(request):
    """Production records page."""
    from production.models import ProductionRecord
    records = ProductionRecord.objects.select_related('flock').filter(user=request.user)[:50]
    return render(request, 'production_records.html', {'records': records})


@login_required(login_url='login')
def production_record_create(request):
    """Create a production record."""
    form = ProductionRecordForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        record = form.save(commit=False)
        record.user = request.user
        record.save()
        create_activity_notification(
            request.user,
            f"Successfully added {record.get_product_type_display().lower()} production record",
            f"Recorded {record.quantity:g} {record.unit} for flock {record.flock.flock_id} on {record.date}.",
            record,
        )
        messages.success(request, 'Production record added.')
        return redirect('production_records')
    return render(request, 'production_record_form.html', {
        'form': form,
        'title': 'Add Production Record',
        'submit_label': 'Save Record',
    })


@login_required(login_url='login')
def production_record_update(request, record_id):
    """Edit a production record."""
    from production.models import ProductionRecord
    record = get_object_or_404(ProductionRecord, pk=record_id, user=request.user)
    form = ProductionRecordForm(request.POST or None, instance=record, user=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Production record updated.')
        return redirect('production_records')
    return render(request, 'production_record_form.html', {
        'form': form,
        'title': 'Edit Production Record',
        'submit_label': 'Update Record',
    })


@login_required(login_url='login')
def production_record_delete(request, record_id):
    """Delete a production record."""
    from production.models import ProductionRecord
    record = get_object_or_404(ProductionRecord, pk=record_id, user=request.user)
    if request.method == 'POST':
        record.delete()
        messages.success(request, 'Production record deleted.')
    return redirect('production_records')


@login_required(login_url='login')
def mortality_records_view(request):
    """Mortality records page."""
    from production.models import MortalityRecord
    records = MortalityRecord.objects.select_related('flock').filter(user=request.user)[:50]
    return render(request, 'mortality_records.html', {'records': records})


@login_required(login_url='login')
def mortality_record_create(request):
    """Create a mortality record."""
    form = MortalityRecordForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        record = form.save(commit=False)
        record.user = request.user
        record.save()
        record.flock.refresh_from_db()
        create_activity_notification(
            request.user,
            "Successfully added mortality record",
            (
                f"Recorded {record.quantity} mortality for flock {record.flock.flock_id} due to "
                f"{record.get_reason_display().lower()}."
            ),
            record,
        )
        messages.success(request, f'Mortality record added. Flock {record.flock.flock_id} was updated.')
        return redirect('mortality_records')
    return render(request, 'mortality_record_form.html', {
        'form': form,
        'title': 'Add Mortality Record',
        'submit_label': 'Save Record',
    })


@login_required(login_url='login')
def mortality_record_update(request, record_id):
    """Edit a mortality record."""
    from production.models import MortalityRecord
    record = get_object_or_404(MortalityRecord, pk=record_id, user=request.user)
    form = MortalityRecordForm(request.POST or None, instance=record, user=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Mortality record updated.')
        return redirect('mortality_records')
    return render(request, 'mortality_record_form.html', {
        'form': form,
        'title': 'Edit Mortality Record',
        'submit_label': 'Update Record',
    })


@login_required(login_url='login')
def mortality_record_delete(request, record_id):
    """Delete a mortality record."""
    from production.models import MortalityRecord
    record = get_object_or_404(MortalityRecord, pk=record_id, user=request.user)
    if request.method == 'POST':
        record.delete()
        messages.success(request, 'Mortality record deleted.')
    return redirect('mortality_records')


@login_required(login_url='login')
def forecasting_view(request):
    """Forecasting page based on the logged-in user's encoded records."""
    from expenses.models import Expense
    from flocks.models import Flock
    from inventory.models import Inventory
    from production.models import ProductionRecord
    from revenue.models import Revenue

    ensure_month_end_forecast_notification(request.user)

    today = timezone.localdate()
    current_month_start = today.replace(day=1)

    def add_months(value, months):
        month_index = value.month - 1 + months
        year = value.year + month_index // 12
        month = month_index % 12 + 1
        return value.replace(year=year, month=month, day=1)

    def month_key(value):
        return value.date() if hasattr(value, 'date') else value

    def decimal_sum(queryset, field):
        return queryset.aggregate(total=Sum(field))['total'] or 0

    def trend_forecast(values, periods=1):
        numeric_values = [float(value) for value in values if value is not None]
        if not numeric_values:
            return [0 for _ in range(periods)]
        if len(numeric_values) == 1:
            return [round(numeric_values[0], 2) for _ in range(periods)]

        recent_window = numeric_values[-3:] if len(numeric_values) >= 3 else numeric_values
        baseline = sum(recent_window) / len(recent_window)
        slope = (numeric_values[-1] - numeric_values[0]) / max(len(numeric_values) - 1, 1)
        return [round(max(0, baseline + slope * step), 2) for step in range(1, periods + 1)]

    history_start = add_months(current_month_start, -5)
    history_months = [add_months(history_start, offset) for offset in range(6)]
    forecast_months = [add_months(current_month_start, offset) for offset in range(1, 4)]

    revenue_by_month = {
        month_key(item['month']): item['total'] or 0
        for item in Revenue.objects.filter(user=request.user, date__gte=history_start)
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(total=Sum('total_amount'))
    }
    expense_by_month = {
        month_key(item['month']): item['total'] or 0
        for item in Expense.objects.filter(user=request.user, date__gte=history_start)
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(total=Sum('amount'))
    }
    production_by_month = {
        month_key(item['month']): item['total'] or 0
        for item in ProductionRecord.objects.filter(
            user=request.user,
            product_type='eggs',
            date__gte=history_start,
        )
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(total=Sum('quantity'))
    }

    revenue_history = [
        float(revenue_by_month[month])
        for month in history_months
        if month in revenue_by_month
    ]
    expense_history = [
        float(expense_by_month[month])
        for month in history_months
        if month in expense_by_month
    ]
    production_history = [
        float(production_by_month[month])
        for month in history_months
        if month in production_by_month
    ]

    revenue_forecast = trend_forecast(revenue_history, 3)
    expense_forecast = trend_forecast(expense_history, 3)
    production_forecast = trend_forecast(production_history, 1)[0]
    expected_profit = round(revenue_forecast[0] - expense_forecast[0], 2)

    active_birds = decimal_sum(
        Flock.objects.filter(user=request.user, status='active'),
        'quantity',
    )
    feed_demand = round(float(active_birds) * 0.12 * 30, 2)
    feed_stock = decimal_sum(
        Inventory.objects.filter(user=request.user, item_type='feed'),
        'quantity',
    )

    encoded_months = len(set(revenue_by_month) | set(expense_by_month) | set(production_by_month))
    confidence = min(95, 45 + encoded_months * 8)

    chart_data = {
        'labels': [capfirst(month.strftime('%b %Y')) for month in history_months + forecast_months],
        'actualRevenue': [
            float(revenue_by_month[month]) if month in revenue_by_month else None
            for month in history_months
        ] + [None for _ in forecast_months],
        'forecastRevenue': [None for _ in history_months] + revenue_forecast,
    }

    return render(request, 'forecasting.html', {
        'revenue_forecast': revenue_forecast[0],
        'expected_profit': expected_profit,
        'feed_demand': feed_demand,
        'feed_stock': feed_stock,
        'production_forecast': production_forecast,
        'forecast_confidence': confidence,
        'chart_data': chart_data,
        'has_encoded_data': any([revenue_history, expense_history, production_history, active_birds]),
    })


def ensure_month_end_forecast_notification(user):
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    if tomorrow.month == today.month:
        return

    month_marker = today.year * 100 + today.month
    notification_exists = user.notifications.filter(
        related_object_type='month_end_forecast',
        related_object_id=month_marker,
    ).exists()
    if notification_exists:
        return

    notification = create_activity_notification(
        user,
        "Month-end forecasting is ready",
        f"Review your month-end forecast for {today:%B %Y}, including projected revenue, profit, feed demand, and production.",
        notification_type='info',
    )
    notification.related_object_type = 'month_end_forecast'
    notification.related_object_id = month_marker
    notification.save(update_fields=['related_object_type', 'related_object_id'])


@login_required(login_url='login')
def scenario_analysis_view(request):
    """Scenario analysis page based on the logged-in user's encoded records."""
    from expenses.models import Expense
    from revenue.models import Revenue

    today = timezone.localdate()
    current_month_start = today.replace(day=1)

    def add_months(value, months):
        month_index = value.month - 1 + months
        year = value.year + month_index // 12
        month = month_index % 12 + 1
        return value.replace(year=year, month=month, day=1)

    def decimal_sum(queryset, field):
        return queryset.aggregate(total=Sum(field))['total'] or 0

    revenue = decimal_sum(
        Revenue.objects.filter(user=request.user, date__gte=current_month_start),
        'total_amount',
    )
    expenses = decimal_sum(
        Expense.objects.filter(user=request.user, date__gte=current_month_start),
        'amount',
    )
    feed_cost = decimal_sum(
        Expense.objects.filter(
            user=request.user,
            date__gte=current_month_start,
        ).filter(Q(expense_type='feed') | Q(category='inventory') | Q(description__icontains='feed')),
        'amount',
    )
    profit = revenue - expenses

    month_starts = [add_months(current_month_start, offset) for offset in range(-5, 1)]
    monthly_profit = []
    for month_start in month_starts:
        next_month_start = add_months(month_start, 1)
        month_revenue = decimal_sum(
            Revenue.objects.filter(
                user=request.user,
                date__gte=month_start,
                date__lt=next_month_start,
            ),
            'total_amount',
        )
        month_expenses = decimal_sum(
            Expense.objects.filter(
                user=request.user,
                date__gte=month_start,
                date__lt=next_month_start,
            ),
            'amount',
        )
        monthly_profit.append({
            'label': month_start.strftime('%b %Y'),
            'revenue': float(month_revenue),
            'expenses': float(month_expenses),
            'profit': float(month_revenue - month_expenses),
        })

    recent_months = monthly_profit[-3:]
    predicted_revenue = sum(month['revenue'] for month in recent_months) / len(recent_months)
    predicted_expenses = sum(month['expenses'] for month in recent_months) / len(recent_months)
    predicted_profit = predicted_revenue - predicted_expenses
    next_month = add_months(current_month_start, 1)

    return render(request, 'scenario_analysis.html', {
        'scenario_metrics': {
            'revenue': revenue,
            'expenses': expenses,
            'profit': profit,
            'feed_cost': feed_cost,
            'predicted_revenue': predicted_revenue,
            'predicted_expenses': predicted_expenses,
            'predicted_profit': predicted_profit,
            'prediction_month': next_month.strftime('%B %Y'),
        },
        'monthly_profit': monthly_profit,
        'has_encoded_data': any([revenue, expenses]),
    })


@login_required(login_url='login')
def notifications_page(request):
    """User notifications page."""
    from notifications.models import Notification
    ensure_month_end_forecast_notification(request.user)
    notifications = Notification.objects.filter(user=request.user)[:50]
    return render(request, 'notifications_page.html', {'notifications': notifications})
