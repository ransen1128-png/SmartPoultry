from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class LogoutSessionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('logout-owner', 'owner@example.com', 'Original-secret!47')
        self.client.force_login(self.user)

    def test_logout_invalidates_server_session_and_old_cookie(self):
        old_cookie = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        response = self.client.get(reverse('logout'))
        self.assertEqual(response['Clear-Site-Data'], '"cache"')
        self.assertRedirects(response, reverse('login'))
        self.assertNotIn('_auth_user_id', self.client.session)
        replay = Client()
        replay.cookies[settings.SESSION_COOKIE_NAME] = old_cookie
        self.assertEqual(replay.get(reverse('session_status')).json(), {'authenticated': False, 'user_id': None})
        self.assertEqual(replay.get(reverse('farm_branches')).status_code, 302)

    def test_json_logout_also_invalidates_session(self):
        response = self.client.post(reverse('logout'), HTTP_ACCEPT='application/json')
        self.assertEqual(response.json(), {'logged_out': True})
        self.assertEqual(response['Clear-Site-Data'], '"cache"')
        self.assertFalse(self.client.get(reverse('session_status')).json()['authenticated'])

    def test_all_sidebar_pages_require_login_after_logout(self):
        self.client.get(reverse('logout'))
        for name in ('dashboard','farm_branches','flocks','production_records','mortality_records','inventory',
                     'revenue','expenses','analytics','rooster_age_estimator','forecasting','scenario_analysis',
                     'reports','activity_history','reliability_status','notifications_page','profile','feedback','settings','admin_dashboard'):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertIn('login', response['Location'])

    def test_api_data_is_unavailable_after_logout(self):
        self.client.get(reverse('logout'))
        for path in ('/api/accounts/users/','/api/inventory/','/api/flocks/','/api/notifications/'):
            with self.subTest(path=path):
                self.assertIn(self.client.get(path).status_code, (401,403))

    def test_private_pages_and_session_responses_are_not_cached(self):
        for url in (reverse('farm_branches'), reverse('profile'), reverse('session_status'), reverse('logout'), reverse('login')):
            with self.subTest(url=url):
                response = self.client.get(url)
                cache = response.get('Cache-Control', '')
                self.assertIn('no-store', cache)
                self.assertIn('private', cache)
                self.assertIn('no-cache', cache)

    def test_session_status_identifies_the_current_account(self):
        self.assertEqual(self.client.get(reverse('session_status')).json(), {'authenticated': True, 'user_id': str(self.user.pk)})
        another = get_user_model().objects.create_user('other-owner', password='Other-secret!47')
        self.client.force_login(another)
        self.assertEqual(self.client.get(reverse('session_status')).json()['user_id'], str(another.pk))

    def test_account_page_loads_history_and_tab_session_guard(self):
        response = self.client.get(reverse('farm_branches'))
        self.assertContains(response, 'auth_session.js?v=20261120')
        self.assertContains(response, f'data-user-id="{self.user.pk}"')
