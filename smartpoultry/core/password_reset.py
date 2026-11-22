"""Email ownership verification using Django's single-use password reset tokens."""
import logging
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView, PasswordResetDoneView
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils.crypto import salted_hmac
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django import forms

from .email_backend import EmailDeliveryError

logger = logging.getLogger(__name__)


class ResetEmailForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].widget.attrs.update({
            'class': 'form-control', 'autocomplete': 'email', 'autofocus': True,
        })

    def get_users(self, email):
        return (user for user in super().get_users(email) if user.is_active_user)

    def send_mail(self, *args, **kwargs):
        try:
            super().send_mail(*args, **kwargs)
        except (EmailDeliveryError, ImproperlyConfigured) as error:
            # Keep the public response the same for existing and unknown accounts.
            # Only sanitized provider errors enter logs; never log a reset token.
            logger.error('Password reset email failed: %s', error)


class ResetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].label = 'New Password'
        self.fields['new_password2'].label = 'Confirm Password'
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
        self.fields['new_password1'].widget.attrs['aria-describedby'] = 'resetPasswordRequirements resetChecklistStatus resetPasswordRequired'
        self.fields['new_password2'].widget.attrs['aria-describedby'] = 'resetPasswordMatch'

    def clean_new_password2(self):
        # Django attaches strength errors to confirmation by default. Keep them
        # beside the new password, and reserve confirmation for matching feedback.
        from django.core.exceptions import ValidationError
        try:
            return super().clean_new_password2()
        except ValidationError as error:
            if any(item.code == 'password_mismatch' for item in error.error_list):
                raise ValidationError('Password not match', code='password_mismatch') from error
            self.add_error('new_password1', error)
            return self.cleaned_data.get('new_password2')


class RecoveryIdentityForm(ResetEmailForm):
    username = forms.CharField(label='Username', max_length=150, widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'username'}))

    def clean(self):
        data = super().clean()
        if data.get('email') and data.get('username'):
            from django.contrib.auth import get_user_model
            if not get_user_model().objects.filter(
                email__iexact=data['email'], username=data['username'],
                is_active=True, is_active_user=True,
            ).exists():
                raise forms.ValidationError('Email and username do not match an active account.')
        return data


@method_decorator(never_cache, name='dispatch')
class RequestPasswordResetView(PasswordResetView):
    template_name = 'forgot_password.html'
    form_class = ResetEmailForm
    email_template_name = 'emails/password_reset.txt'
    subject_template_name = 'emails/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')

    def mode(self):
        return 'email' if settings.PASSWORD_RESET_METHOD == 'email' else 'questions'

    def get_form_class(self):
        return RecoveryIdentityForm if self.mode() == 'questions' else self.form_class

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'question_recovery': self.mode() == 'questions'}

    def post(self, request, *args, **kwargs):
        if self.mode() == 'questions':
            # A failed new attempt must not retain a previous account challenge
            # or an earlier permission to change a password in this browser.
            request.session.pop('recovery_challenge', None)
            request.session.pop('recovery_grant', None)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        if self.mode() == 'questions':
            self.request.session.pop('recovery_grant', None)
            from django.utils import timezone
            self.request.session['recovery_challenge'] = {
                'email': form.cleaned_data['email'], 'username': form.cleaned_data['username'],
                'expires': timezone.now().timestamp() + 600,
            }
            return HttpResponseRedirect(reverse_lazy('recovery_questions'))
        if settings.EMAIL_BACKEND == 'core.email_backend.ResendEmailBackend' and not (
            settings.RESEND_API_KEY and settings.DEFAULT_FROM_EMAIL
        ):
            form.add_error(None, 'Password reset emails are temporarily unavailable. Please try again later.')
            return self.form_invalid(form)

        origin = urlsplit(settings.PASSWORD_RESET_BASE_URL)
        if settings.PASSWORD_RESET_BASE_URL and (
            origin.scheme not in ('http', 'https') or not origin.netloc
            or origin.username or origin.password or origin.query or origin.fragment
            or origin.path not in ('', '/')
            or (origin.scheme == 'http' and origin.hostname not in ('localhost', '127.0.0.1', '[::1]', '::1'))
        ):
            form.add_error(None, 'Password reset emails are temporarily unavailable. Please try again later.')
            logger.error('PASSWORD_RESET_BASE_URL must be an HTTPS site origin (HTTP is allowed only on localhost).')
            return self.form_invalid(form)

        # Per-email cooldown prevents repeated clicks from flooding an inbox.
        # Unknown addresses take the same path and get the same confirmation.
        key = 'password-reset:' + salted_hmac('password-reset-cooldown', form.cleaned_data['email'].casefold()).hexdigest()
        if cache.add(key, True, timeout=60):
            form.save(
                request=self.request,
                domain_override=origin.netloc or None,
                use_https=origin.scheme == 'https' if origin.netloc else self.request.is_secure(),
                email_template_name=self.email_template_name,
                subject_template_name=self.subject_template_name,
            )
        return HttpResponseRedirect(self.success_url)


class ResetRequestDoneView(PasswordResetDoneView):
    template_name = 'password_reset_done.html'

class ConfirmPasswordResetView(PasswordResetConfirmView):
    template_name = 'password_reset_confirm.html'
    form_class = ResetPasswordForm
    success_url = reverse_lazy('password_reset_complete')
    post_reset_login = False

    def get_user(self, uidb64):
        user = super().get_user(uidb64)
        return user if user and user.is_active and user.is_active_user else None

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        response['Referrer-Policy'] = 'same-origin'
        return response
