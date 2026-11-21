import importlib.util
import unittest

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import TestCase, override_settings


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SettingsNavigationTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('settings-navigation',password='Original-secret!79')
        self.client.force_login(self.user)

    def test_default_settings_and_profile_link_open_security(self):
        for path in ('/settings/','/settings/?tab=security','/settings/?tab=unknown'):
            with self.subTest(path=path):
                response=self.client.get(path)
                self.assertEqual(response.context['active_settings_tab'],'security')
        self.assertContains(self.client.get('/profile/'),'href="/settings/?tab=security"')

    def test_notification_preferences_remain_directly_accessible(self):
        response=self.client.get('/settings/?tab=notifications')
        self.assertEqual(response.context['active_settings_tab'],'notifications')
        self.assertContains(response,'Notification Preferences')

    def test_saving_notifications_returns_to_preferences(self):
        response=self.client.post('/settings/',{'action':'notifications','email_alerts':'on'},follow=True)
        self.assertRedirects(response,'/settings/?tab=notifications')
        self.assertEqual(response.context['active_settings_tab'],'notifications')

    def test_password_errors_keep_security_active(self):
        response=self.client.post('/settings/?tab=notifications',{'action':'password','current_password':'wrong',
            'new_password':'Replacement!79','confirm_password':'Replacement!79'})
        self.assertEqual(response.context['active_settings_tab'],'security')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Original-secret!79'))


@unittest.skipUnless(importlib.util.find_spec('playwright'),'Desktop Playwright is not installed')
@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SettingsNavigationBrowserTests(StaticLiveServerTestCase):
    def test_profile_sidebar_and_tab_refresh_navigation(self):
        from playwright.sync_api import sync_playwright, Error, expect
        user=get_user_model().objects.create_user('settings-browser',password='Original-secret!79')
        self.client.force_login(user)
        session=self.client.cookies['sessionid'].value
        with sync_playwright() as playwright:
            try:browser=playwright.chromium.launch(channel='chrome',headless=True)
            except Error as error:raise unittest.SkipTest(str(error))
            try:
                page=browser.new_page(viewport={'width':390,'height':844})
                errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                page.context.add_cookies([{'name':'sessionid','value':session,'url':self.live_server_url}])
                page.goto(self.live_server_url+'/profile/',wait_until='networkidle')
                page.get_by_role('link',name='Account Settings',exact=True).click()
                expect(page.locator('#security-panel')).to_be_visible()
                expect(page.locator('#security-tab')).to_have_attribute('aria-selected','true')
                page.get_by_role('tab',name='Notification Preferences',exact=True).click()
                page.wait_for_url('**/settings/?tab=notifications')
                page.reload(wait_until='networkidle')
                expect(page.locator('#notifications-panel')).to_be_visible()
                page.goto(self.live_server_url+'/settings/',wait_until='networkidle')
                expect(page.locator('#security-panel')).to_be_visible()
                expect(page.locator('#notifications-panel')).not_to_be_visible()
                self.assertEqual(errors,[])
            finally:browser.close()
