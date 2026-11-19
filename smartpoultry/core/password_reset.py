"""Email ownership verification using Django's single-use password reset tokens."""
import logging
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils.crypto import salted_hmac
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

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


@method_decorator(never_cache, name='dispatch')
class RequestPasswordResetView(PasswordResetView):
    template_name = 'forgot_password.html'
    form_class = ResetEmailForm
    email_template_name = 'emails/password_reset.txt'
    subject_template_name = 'emails/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')

    def form_valid(self, form):
        if settings.EMAIL_BACKEND == 'core.email_backend.ResendEmailBackend' and not (
            settings.RESEND_API_KEY and settings.DEFAULT_FROM_EMAIL
        ):
            form.add_error(None, 'Password reset emails are temporarily unavailable. Please contact the administrator.')
            return self.form_invalid(form)

        origin = urlsplit(settings.PASSWORD_RESET_BASE_URL)
        if settings.PASSWORD_RESET_BASE_URL and (
            origin.scheme not in ('http', 'https') or not origin.netloc
            or origin.username or origin.password or origin.query or origin.fragment
            or origin.path not in ('', '/')
            or (origin.scheme == 'http' and origin.hostname not in ('localhost', '127.0.0.1', '[::1]', '::1'))
        ):
            form.add_error(None, 'Password reset emails are temporarily unavailable. Please contact the administrator.')
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
