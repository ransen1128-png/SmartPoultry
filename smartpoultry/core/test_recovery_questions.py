from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import AccountRecovery, PasswordResetRequest
from .recovery_questions import RecoverySetupForm


@override_settings(PASSWORD_RESET_METHOD='questions', PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class RecoveryQuestionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.details = {'username': 'question-owner', 'email': 'owner@example.com',
            'password': 'Original-secret!47', 'password2': 'Original-secret!47',
            'question_one': 'school_trip', 'answer_one': 'Private mountain trip',
            'question_two': 'stuffed_toy', 'answer_two': 'Purple toy dragon'}
        self.user = get_user_model().objects.create_user(username='question-owner', email='owner@example.com', password='Original-secret!47')
        form = RecoverySetupForm(self.details)
        self.assertTrue(form.is_valid())
        self.profile = form.save(self.user)

    def challenge(self):
        return self.client.post(reverse('forgot_password'), {'username': self.user.username, 'email': self.user.email}, follow=True)

    def answer(self, one='Private mountain trip', two='Purple toy dragon'):
        cache.clear()
        return self.client.post(reverse('recovery_questions'), {'answer_one': one, 'answer_two': two}, follow=True)

    def test_registration_requires_recovery_and_stores_hashes(self):
        details = {**self.details, 'username': 'new-owner', 'email': 'new@example.com'}
        response = self.client.post(reverse('register'), details, follow=True)
        self.assertContains(response, 'Account Created Successfully!')
        self.assertNotIn('_auth_user_id', self.client.session)
        profile = AccountRecovery.objects.get(user__username='new-owner')
        self.assertNotEqual(profile.answer_one_hash, details['answer_one'])
        self.assertNotIn(details['answer_one'], profile.answer_one_hash)
        self.assertNotIn('new@example.com', self.client.session.get('recovery_challenge', {}))

    def test_registration_missing_answers_cannot_create_account(self):
        details = {**self.details, 'username': 'incomplete', 'email': 'incomplete@example.com', 'answer_two': ''}
        self.assertContains(self.client.post(reverse('register'), details), 'Complete both recovery questions')
        self.assertFalse(get_user_model().objects.filter(username='incomplete').exists())

    def test_questions_and_answers_must_be_distinct(self):
        for changed in ({'question_two': 'school_trip'}, {'answer_two': self.details['answer_one']}, {'answer_one': '123456'}):
            self.assertFalse(RecoverySetupForm({**self.details, **changed}).is_valid())

    def test_wrong_answers_block_password_form_and_change(self):
        self.challenge()
        response = self.answer('wrong answer', 'wrong answer')
        self.assertContains(response, 'answers could not be verified')
        self.assertNotIn('recovery_grant', self.client.session)
        response = self.client.post(reverse('question_password_reset'), {'new_password1': 'Attack-secret!47', 'new_password2': 'Attack-secret!47'})
        self.assertContains(response, 'Reset Link Unavailable')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Original-secret!47'))

    def test_correct_answers_allow_single_use_password_change(self):
        response = self.challenge()
        self.assertContains(response, 'most memorable school field trip')
        response = self.answer('  PRIVATE   mountain TRIP ', 'purple TOY dragon')
        self.assertContains(response, 'Choose a New Password')
        grant = self.client.session['recovery_grant']
        self.assertNotIn('Private mountain trip', grant)
        response = self.client.post(reverse('question_password_reset'), {'new_password1': 'Updated-secret!79', 'new_password2': 'Updated-secret!79'}, follow=True)
        self.assertContains(response, 'Password Updated Successfully!')
        self.assertNotIn('recovery_grant', self.client.session)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Updated-secret!79'))
        session = self.client.session; session['recovery_grant'] = grant; session.save()
        self.assertContains(self.client.get(reverse('question_password_reset')), 'Reset Link Unavailable')

    def test_lockout_survives_cache_clear_and_expires(self):
        self.challenge()
        for _ in range(5):
            self.answer('incorrect answer', 'incorrect answer')
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.failed_attempts, 5)
        self.assertIsNotNone(self.profile.locked_until)
        self.assertContains(self.answer(), 'answers could not be verified')
        AccountRecovery.objects.filter(pk=self.profile.pk).update(locked_until=timezone.now() - timedelta(seconds=1))
        self.assertContains(self.answer(), 'Choose a New Password')

    def test_grant_expires_in_ten_minutes(self):
        self.challenge(); self.answer()
        from time import time
        with patch('django.core.signing.time.time', return_value=time() + 601):
            self.assertContains(self.client.get(reverse('question_password_reset')), 'Reset Link Unavailable')

    def test_disabled_user_cannot_recover(self):
        self.user.is_active = False; self.user.save()
        self.assertContains(self.challenge(), 'Email and username do not match an active account.')
        self.assertNotIn('recovery_challenge', self.client.session)
        self.assertNotIn('recovery_grant', self.client.session)

    def test_username_and_email_must_match_the_same_account(self):
        other = get_user_model().objects.create_user('other-owner', 'other@example.com', 'Other-secret!47')
        cases = [
            (self.user.email, 'wrong-username'),
            ('wrong@example.com', self.user.username),
            (self.user.email, other.username),
            (other.email, self.user.username),
        ]
        for email, username in cases:
            with self.subTest(email=email, username=username):
                response = self.client.post(reverse('forgot_password'), {'email': email, 'username': username})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'Email and username do not match an active account.')
                self.assertNotIn('recovery_challenge', self.client.session)
                self.assertRedirects(self.client.get(reverse('recovery_questions')), reverse('forgot_password'))

    def test_failed_identity_attempt_clears_earlier_verification(self):
        self.challenge(); self.answer()
        self.assertIn('recovery_grant', self.client.session)
        response = self.client.post(reverse('forgot_password'), {'email': self.user.email, 'username': 'wrong-username'})
        self.assertContains(response, 'Email and username do not match an active account.')
        self.assertNotIn('recovery_grant', self.client.session)
        self.assertNotIn('recovery_challenge', self.client.session)
        self.assertContains(self.client.get(reverse('question_password_reset')), 'Reset Link Unavailable')

    def test_invalid_form_also_clears_previous_challenge(self):
        self.challenge()
        self.assertIn('recovery_challenge', self.client.session)
        self.client.post(reverse('forgot_password'), {'email': self.user.email, 'username': ''})
        self.assertNotIn('recovery_challenge', self.client.session)

    def test_email_case_differences_are_accepted_with_correct_username(self):
        response = self.client.post(reverse('forgot_password'), {'email': 'OWNER@EXAMPLE.COM', 'username': self.user.username}, follow=True)
        self.assertContains(response, 'Answer Your Recovery Questions')
        self.assertIn('recovery_challenge', self.client.session)

    def test_admin_must_supply_correct_answers_and_never_sees_saved_answers(self):
        admin = get_user_model().objects.create_superuser('testadmin', 'admin@example.com', 'Admin-secret!47')
        self.client.force_login(admin)
        url = reverse('admin_reset_user_password', args=[self.user.pk])
        response = self.client.get(url)
        self.assertContains(response, 'most memorable school field trip')
        self.assertNotContains(response, self.details['answer_one'])
        self.assertNotContains(response, self.profile.answer_one_hash)
        data = {'new_password': 'Admin-updated!79', 'confirm_password': 'Admin-updated!79', 'identity_verified': 'yes', 'answer_one': 'incorrect', 'answer_two': 'incorrect'}
        self.client.post(url, data)
        self.user.refresh_from_db(); self.assertTrue(self.user.check_password('Original-secret!47'))
        self.client.post(url, {**data, 'answer_one': self.details['answer_one'], 'answer_two': self.details['answer_two']})
        self.user.refresh_from_db(); self.assertTrue(self.user.check_password('Admin-updated!79'))

    def test_old_accounts_can_notify_admin_without_email_provider(self):
        self.profile.delete()
        for _ in range(2):
            response = self.client.post(reverse('request_admin_password_reset'), {'email': self.user.email}, follow=True)
            self.assertContains(response, 'Request Submitted')
        self.assertEqual(PasswordResetRequest.objects.filter(user=self.user, status='pending').count(), 1)
        admin = get_user_model().objects.create_superuser('testadmin', 'admin@example.com', 'Admin-secret!47')
        self.client.force_login(admin)
        data = self.client.get(reverse('admin_notifications_poll')).json()
        self.assertEqual(data['reset_count'], 1)
        self.assertEqual(data['requests'][0]['username'], self.user.username)
        page = self.client.get(reverse('admin_dashboard'))
        self.assertContains(page, 'Password reset requested by question-owner')
        url = reverse('admin_reset_user_password', args=[self.user.pk])
        passwords = {'new_password': 'Admin-updated!79', 'confirm_password': 'Admin-updated!79'}
        self.client.post(url, passwords)
        self.user.refresh_from_db(); self.assertTrue(self.user.check_password('Original-secret!47'))
        self.client.post(url, {**passwords, 'identity_verified': 'yes'})
        self.assertEqual(self.client.get(reverse('admin_notifications_poll')).json()['reset_count'], 0)

    def test_nonadmins_cannot_read_requests_or_bell_data(self):
        for client in (Client(), self.client):
            if client is self.client:
                client.force_login(self.user)
            for name in ('admin_notifications_poll', 'admin_password_reset_requests'):
                self.assertEqual(client.get(reverse(name)).status_code, 302)

    def test_unknown_email_admin_request_does_not_reveal_account(self):
        known = self.client.post(reverse('request_admin_password_reset'), {'email': self.user.email}, follow=True)
        unknown = self.client.post(reverse('request_admin_password_reset'), {'email': 'unknown@example.com'}, follow=True)
        self.assertEqual(known.content, unknown.content)

    def test_admin_cannot_elevate_to_reset_superuser(self):
        staff = get_user_model().objects.create_user('staffadmin', password='Admin-secret!47', is_staff=True)
        root = get_user_model().objects.create_superuser('rootadmin', 'root@example.com', 'Root-secret!47')
        self.client.force_login(staff)
        self.assertEqual(self.client.post(reverse('admin_reset_user_password', args=[root.pk]), {'new_password': 'Attack!79', 'confirm_password': 'Attack!79'}).status_code, 403)
