import calendar
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
from django.db.models import Count, Min, Q, Sum
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
    try:
        selected_year = int(request.GET.get('year', today.year))
        selected_month = int(request.GET.get('month', today.month))
        if not 1 <= selected_year <= 9999 or not 1 <= selected_month <= 12:
            raise ValueError
    except (TypeError, ValueError):
        selected_year, selected_month = today.year, today.month

    current_month_start = date(selected_year, selected_month, 1)
    if selected_month == 12:
        next_month_start = date(selected_year + 1, 1, 1) if selected_year < 9999 else date.max
    else:
        next_month_start = date(selected_year, selected_month + 1, 1)
    previous_month_start = (current_month_start - timedelta(days=1)).replace(day=1)

    branches = Branch.objects.filter(farm__owner=request.user)
    selected_branch_id = request.GET.get('branch', '')
    selected_branch = branches.filter(pk=selected_branch_id).first() if selected_branch_id.isdigit() else None

    def records_for_period(model, start, end, **filters):
        queryset = model.objects.filter(
            user=request.user,
            date__gte=start,
            date__lt=end,
            **filters,
        )
        if selected_branch:
            queryset = queryset.filter(branch=selected_branch)
        return queryset

    def decimal_sum(queryset, field):
        return queryset.aggregate(total=Sum(field))['total'] or 0

    def percent_change(current, previous):
        if not previous:
            return None
        return round(((current - previous) / previous) * 100, 1)

    current_revenue = decimal_sum(records_for_period(Revenue, current_month_start, next_month_start), 'total_amount')
    previous_revenue = decimal_sum(
        records_for_period(Revenue, previous_month_start, current_month_start),
        'total_amount',
    )
    current_expenses = decimal_sum(records_for_period(Expense, current_month_start, next_month_start), 'amount')
    previous_expenses = decimal_sum(
        records_for_period(Expense, previous_month_start, current_month_start),
        'amount',
    )
    current_profit = current_revenue - current_expenses
    previous_profit = previous_revenue - previous_expenses
    feed_cost = decimal_sum(
        records_for_period(Expense, current_month_start, next_month_start, expense_type='feed'),
        'amount',
    )
    production_total = decimal_sum(
        records_for_period(ProductionRecord, current_month_start, next_month_start, product_type='eggs'),
        'quantity',
    )
    mortality_total = records_for_period(MortalityRecord, current_month_start, next_month_start).aggregate(
        total=Sum('quantity')
    )['total'] or 0
    active_flocks_query = Flock.objects.filter(user=request.user, status='active')
    if selected_branch:
        active_flocks_query = active_flocks_query.filter(branch=selected_branch)
    total_birds = active_flocks_query.aggregate(total=Sum('quantity'))['total'] or 0
    active_flocks = active_flocks_query.count()
    mortality_rate = round((mortality_total / total_birds) * 100, 2) if total_birds else 0
    feed_stock = decimal_sum(Inventory.objects.filter(user=request.user, item_type='feed'), 'quantity')
    feed_expense_share = round((feed_cost / current_expenses) * 100, 1) if current_expenses else 0

    chart_months = []
    for offset in range(5, -1, -1):
        month_index = selected_month - 1 - offset
        chart_months.append(date(selected_year + month_index // 12, month_index % 12 + 1, 1))
    trend_start = chart_months[0]

    def month_key(value):
        return value.date() if hasattr(value, 'date') else value

    revenue_by_month = {
        month_key(item['month']): item['total'] or 0
        for item in records_for_period(Revenue, trend_start, next_month_start)
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(total=Sum('total_amount'))
    }
    expenses_by_month = {
        month_key(item['month']): item['total'] or 0
        for item in records_for_period(Expense, trend_start, next_month_start)
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(total=Sum('amount'))
    }
    feed_by_month = {
        month_key(item['month']): item['total'] or 0
        for item in records_for_period(Expense, trend_start, next_month_start, expense_type='feed')
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(total=Sum('amount'))
    }

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

    earliest_dates = [
        model.objects.filter(user=request.user).aggregate(first_date=Min('date'))['first_date']
        for model in (Revenue, Expense, ProductionRecord, MortalityRecord)
    ]
    earliest_year = min((value.year for value in earliest_dates if value), default=today.year)
    context = {
        'date_range_label': current_month_start.strftime('%B %Y'),
        'selected_period_label': current_month_start.strftime('%B %Y'),
        'branches': branches,
        'selected_branch': selected_branch,
        'selected_month': selected_month,
        'selected_year': selected_year,
        'month_options': [(month, calendar.month_name[month]) for month in range(1, 13)],
        'year_options': reversed(range(max(earliest_year, 1), min(today.year, 9998) + 1)),
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
    branches = []
    try:
        branches = list(request.user.owned_farm.branches.all())
    except Farm.DoesNotExist:
        pass
    return render(request, 'inventory.html', {
        'branches': branches,
        'today': timezone.localdate(),
    })


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
            'summary': f'Technical image quality is adequate ({width}x{height}, brightness and detail checks passed).',
            'penalty': 0,
        }

    penalty = 2 if len(quality_flags) >= 3 else 1
    return {
        'quality': 'limited',
        'summary': f'Technical image quality may limit visual assessment ({width}x{height}; {", ".join(quality_flags)}).',
        'penalty': penalty,
    }


@login_required(login_url='login')
def rooster_age_estimator_view(request):
    """Save rooster photos without claiming analysis until a trained vision model is configured."""
    from core.rooster_age_classifier import model_is_ready, predict_rooster_age

    results = []

    if request.method == 'POST':
        photos = request.FILES.getlist('photos')
        if not photos:
            messages.error(request, 'Upload at least one image to continue.')

        for index, photo in enumerate(photos):
            photo_analysis = analyze_rooster_photo(photo)
            photo_name = photo.name
            prediction = None
            if photo_analysis['quality'] == 'good':
                try:
                    prediction = predict_rooster_age(photo)
                except (OSError, ValueError):
                    prediction = None

            if prediction:
                age_range = prediction['age_range']
                confidence = prediction['confidence']
                evidence = (
                    f"Validated spur-image classifier assigned this image to {age_range}. "
                    f"Bird-separated holdout balanced accuracy: {prediction['balanced_accuracy']:.0%}."
                )
                reasoning = 'The validated classifier compares spur close-up image features with the labeled age ranges.'
                limitations = (
                    'The classifier does not independently confirm a chicken or spur is present, does not measure spur '
                    'length, and does not determine exact age. Breed, trimming, injury, and image angle may affect results.'
                )
            else:
                age_range = 'Insufficient evidence'
                confidence = 'Low'
                reasoning = 'No supported age estimate can be made from this upload.'
                if photo_analysis['quality'] != 'good':
                    evidence = 'Image quality is limited; upload a clear, well-lit close-up of the spur.'
                    limitations = f"{photo_analysis['summary']} No age estimate is provided."
                else:
                    evidence = 'Spur characteristics were not assessed because no validated age model is available.'
                    limitations = (
                        'No validated chicken/spur age model is configured. Technical image-quality checks do not '
                        'detect chickens, measure spurs, or validate age. No age estimate is provided.'
                    )

            record_data = {
                'user': request.user,
                'photo_name': photo_name,
                'chicken_detected': 'unassessed',
                'spur_visibility': 'unassessed',
                'spur_length': 'unassessed',
                'spur_thickness': 'unassessed',
                'spur_point_shape': 'unassessed',
                'spur_curvature': 'unassessed',
                'secondary_clues': '',
                'estimated_age_range': age_range,
                'spur_observations': evidence,
                'reasoning': reasoning,
                'confidence': confidence,
                'limitations': limitations,
            }
            record_data['photo'] = photo
            record = RoosterAgeEstimate.objects.create(**record_data)

            results.append({
                'number': index + 1,
                'id': record.id,
                'photo_name': photo_name,
                'chicken_detected': record.get_chicken_detected_display(),
                'spur_visibility': record.get_spur_visibility_display(),
                'spur_length_assessment': 'Not measured; the classifier predicts age range only and no scale reference is configured.',
                'estimated_age_range': record.estimated_age_range,
                'spur_observations': evidence,
                'image_assessment': photo_analysis['summary'],
                'reasoning': record.reasoning,
                'confidence': record.confidence,
                'limitations': record.limitations,
            })

        if results:
            if model_is_ready():
                messages.success(request, f"Analyzed {len(results)} uploaded image{'s' if len(results) != 1 else ''}.")
            else:
                messages.info(request, f"Saved {len(results)} photo{'s' if len(results) != 1 else ''}. Age estimates remain unavailable until a model passes validation.")

    saved_estimates = RoosterAgeEstimate.objects.filter(user=request.user).exclude(photo='')[:20]
    return render(request, 'rooster_age_estimator.html', {
        'results': results,
        'saved_estimates': saved_estimates,
        'model_ready': model_is_ready(),
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
