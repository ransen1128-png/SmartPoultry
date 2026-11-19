import json
import re
from datetime import datetime, timedelta
from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .email_backend import ResendEmailBackend, EmailDeliveryError


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='SmartPoultry <noreply@example.com>',
    PASSWORD_RESET_BASE_URL='', PASSWORD_RESET_TIMEOUT=1800,
    PASSWORD_RESET_METHOD='email',
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class PasswordResetTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username='reset-owner', email='owner@example.com', password='Old-secret!47',
        )

    def request_reset(self, email='owner@example.com', **data):
        return self.client.post(reverse('forgot_password'), {'email': email, **data}, follow=True)

    def link(self):
        return urlsplit(re.search(r'https?://[^\s]+', mail.outbox[-1].body)[0])

    def test_email_only_cannot_replace_password_without_token(self):
        response = self.request_reset(new_password='Attacker-secret!47', confirm_password='Attacker-secret!47')
        self.assertContains(response, 'Check Your Email')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Old-secret!47'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['owner@example.com'])
        self.assertEqual(self.link().netloc, 'testserver')
        self.assertEqual(self.link().scheme, 'http')

    def test_unknown_and_known_emails_get_identical_confirmation(self):
        known = self.request_reset()
        unknown = self.request_reset('unknown@example.com')
        self.assertEqual(known.content, unknown.content)
        self.assertEqual(len(mail.outbox), 1)

    def test_reset_round_trip_token_single_use_and_no_auto_login(self):
        self.request_reset()
        link = self.link().path
        response = self.client.get(link, follow=True)
        self.assertTrue(response.context['validlink'])
        self.assertNotEqual(response.request['PATH_INFO'], link)
        self.assertEqual(response['Referrer-Policy'], 'same-origin')
        response = self.client.post(response.request['PATH_INFO'], {
            'new_password1': 'Updated-secret!79', 'new_password2': 'Updated-secret!79',
        }, follow=True)
        self.assertContains(response, 'Password Updated Successfully!')
        self.assertNotIn('_auth_user_id', self.client.session)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Updated-secret!79'))
        reused = Client().get(link, follow=True)
        self.assertContains(reused, 'Reset Link Unavailable')

    def test_token_expires_after_thirty_minutes(self):
        then = datetime(2026, 11, 19, 12, 0)
        with patch.object(default_token_generator, '_now', return_value=then):
            self.request_reset()
        with patch.object(default_token_generator, '_now', return_value=then + timedelta(seconds=1801)):
            response = self.client.get(self.link().path, follow=True)
        self.assertContains(response, 'Reset Link Unavailable')

    def test_invalid_token_and_direct_confirm_post_cannot_change_password(self):
        for path in ('/reset-password/not-a-user/fake-token/', '/reset-password/MQ/set-password/'):
            response = self.client.post(path, {'new_password1': 'Attack!47', 'new_password2': 'Attack!47'})
            self.assertContains(response, 'Reset Link Unavailable')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Old-secret!47'))

    def test_password_validation_and_confirmation_still_apply(self):
        self.request_reset()
        response = self.client.get(self.link().path, follow=True)
        path = response.request['PATH_INFO']
        response = self.client.post(path, {'new_password1': '123123', 'new_password2': '123123'})
        self.assertTrue(response.context['form'].errors)
        response = self.client.post(path, {'new_password1': 'Updated!79', 'new_password2': 'Different!79'})
        self.assertTrue(response.context['form'].errors)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Old-secret!47'))

    def test_disabled_account_receives_no_email(self):
        for field in ('is_active', 'is_active_user'):
            cache.clear()
            setattr(self.user, field, False)
            self.user.save()
            self.assertContains(self.request_reset(), 'Check Your Email')
            self.assertEqual(len(mail.outbox), 0)
            setattr(self.user, field, True)

    def test_disabled_account_cannot_use_earlier_link(self):
        self.request_reset()
        self.user.is_active = False
        self.user.save()
        self.assertContains(self.client.get(self.link().path, follow=True), 'Reset Link Unavailable')

    def test_repeated_requests_are_throttled_case_insensitively(self):
        self.request_reset()
        self.request_reset('OWNER@EXAMPLE.COM')
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(PASSWORD_RESET_BASE_URL='https://farm.example.com')
    def test_canonical_https_origin_behind_render_proxy(self):
        self.request_reset()
        self.assertEqual(self.link().scheme, 'https')
        self.assertEqual(self.link().netloc, 'farm.example.com')

    @override_settings(PASSWORD_RESET_BASE_URL='http://farm.example.com')
    def test_insecure_production_origin_is_rejected(self):
        with self.assertLogs('core.password_reset', level='ERROR'):
            response = self.request_reset()
        self.assertContains(response, 'temporarily unavailable')
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND='core.email_backend.ResendEmailBackend', RESEND_API_KEY='')
    def test_missing_provider_is_reported_without_claiming_email_was_sent(self):
        response = self.request_reset()
        self.assertContains(response, 'temporarily unavailable')
        self.assertNotContains(response, 'Check Your Email')

    @override_settings(EMAIL_BACKEND='core.email_backend.ResendEmailBackend', RESEND_API_KEY='test-key')
    def test_provider_failure_is_logged_without_disclosing_accounts(self):
        with patch('core.email_backend.urlopen', side_effect=URLError('private details')):
            with self.assertLogs('core.password_reset', level='ERROR') as logs:
                known = self.request_reset()
            unknown = self.request_reset('unknown@example.com')
        self.assertEqual(known.content, unknown.content)
        self.assertNotIn('private details', str(logs.output))
        self.assertNotIn('owner@example.com', str(logs.output))
        self.assertNotIn('test-key', str(logs.output))

    def test_request_requires_csrf_token(self):
        response = Client(enforce_csrf_checks=True).post(reverse('forgot_password'), {'email': 'owner@example.com'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(len(mail.outbox), 0)

    def test_request_accepts_valid_same_origin_csrf_post(self):
        client = Client(enforce_csrf_checks=True)
        client.get(reverse('forgot_password'), secure=True)
        response = client.post(reverse('forgot_password'), {
            'email': 'owner@example.com',
            'csrfmiddlewaretoken': client.cookies['csrftoken'].value,
        }, secure=True, HTTP_ORIGIN='https://testserver')
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)


@override_settings(RESEND_API_KEY='private-test-key', DEFAULT_FROM_EMAIL='SmartPoultry <noreply@example.com>', EMAIL_TIMEOUT=10)
class ResendBackendTests(SimpleTestCase):
    def message(self):
        return EmailMultiAlternatives('Reset password', 'A private reset link', to=['owner@example.com'])

    @patch('core.email_backend.urlopen')
    def test_https_payload_and_success(self, opener):
        opener.return_value.__enter__.return_value.read.return_value = b'{"id":"accepted-id"}'
        self.assertEqual(ResendEmailBackend().send_messages([self.message()]), 1)
        request = opener.call_args.args[0]
        self.assertEqual(request.full_url, 'https://api.resend.com/emails')
        payload = json.loads(request.data)
        self.assertEqual(payload['to'], ['owner@example.com'])
        self.assertEqual(payload['from'], 'SmartPoultry <noreply@example.com>')
        self.assertEqual(opener.call_args.kwargs['timeout'], 10)

    @patch('core.email_backend.urlopen')
    def test_provider_rejection_is_sanitized_and_never_counted_as_sent(self, opener):
        opener.side_effect = HTTPError('https://api.resend.com/emails', 403, 'private-key-or-token', {}, BytesIO(b'private payload'))
        with self.assertRaisesRegex(EmailDeliveryError, '^Email service returned HTTP 403.$'):
            ResendEmailBackend().send_messages([self.message()])
        self.assertEqual(ResendEmailBackend(fail_silently=True).send_messages([self.message()]), 0)

    @patch('core.email_backend.urlopen')
    def test_acceptance_id_is_required(self, opener):
        opener.return_value.__enter__.return_value.read.return_value = b'{}'
        with self.assertRaises(EmailDeliveryError):
            ResendEmailBackend().send_messages([self.message()])
