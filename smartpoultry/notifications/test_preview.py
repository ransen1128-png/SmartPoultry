import importlib.util
import unittest

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import TestCase, override_settings
from django.urls import reverse

from notifications.models import Notification


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class NotificationPreviewTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('bell-owner',password='Secret!123')
        self.other=get_user_model().objects.create_user('other-bell-owner',password='Secret!123')
        self.client.force_login(self.user)

    def test_latest_five_are_owner_scoped_and_preview_does_not_mark_read(self):
        for index in range(7):
            Notification.objects.create(user=self.user,title=f'Own alert {index}',message='Private farm update',is_read=index<2)
        Notification.objects.create(user=self.other,title='Another account alert',message='Private')
        response=self.client.get(reverse('notification_preview'))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['unread_count'],5)
        self.assertEqual([row['title'] for row in response.json()['results']],[f'Own alert {index}' for index in range(6,1,-1)])
        self.assertEqual(Notification.objects.filter(user=self.user,is_read=False).count(),5)
        self.assertIn('no-store',response['Cache-Control'])

    def test_empty_preview_and_non_get_requests(self):
        self.assertEqual(self.client.get(reverse('notification_preview')).json(),{'unread_count':0,'results':[]})
        self.assertEqual(self.client.post(reverse('notification_preview')).status_code,405)

    def test_anonymous_preview_requires_login(self):
        self.client.logout()
        response=self.client.get(reverse('notification_preview'))
        self.assertEqual(response.status_code,302)
        self.assertTrue(response.url.startswith('/login/'))


@unittest.skipUnless(importlib.util.find_spec('playwright'),'Desktop Playwright is not installed')
@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class NotificationBellBrowserTests(StaticLiveServerTestCase):
    def test_hover_click_latest_five_and_full_page_on_desktop_and_mobile(self):
        from playwright.sync_api import sync_playwright, Error, expect
        user=get_user_model().objects.create_user('bell-browser',password='Secret!123')
        for index in range(7):
            Notification.objects.create(user=user,title=f'Farm update {index}',message='Flock activity recorded.')
        self.client.force_login(user)
        session=self.client.cookies['sessionid'].value
        with sync_playwright() as playwright:
            try:browser=playwright.chromium.launch(channel='chrome',headless=True)
            except Error as error:raise unittest.SkipTest(str(error))
            try:
                page=browser.new_page(viewport={'width':1440,'height':1000})
                errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                page.context.add_cookies([{'name':'sessionid','value':session,'url':self.live_server_url}])
                page.goto(self.live_server_url+'/profile/',wait_until='networkidle')
                bell=page.locator('#userNotificationBell')
                expect(page.locator('#userNotificationCount')).to_have_text('7')
                bell.hover();expect(page.get_by_role('tooltip')).to_have_text('Notifications')
                self.assertTrue(page.url.endswith('/profile/'))
                bell.click()
                expect(page.locator('#userNotificationMenu')).to_be_visible()
                expect(page.locator('.notification-preview-item')).to_have_count(5)
                expect(page.locator('.notification-preview-title').first).to_have_text('Farm update 6')
                self.assertTrue(page.url.endswith('/profile/'))
                page.keyboard.press('Escape')
                expect(page.locator('#userNotificationMenu')).not_to_be_visible()
                page.set_viewport_size({'width':390,'height':844})
                bell.click();expect(page.locator('#userNotificationMenu')).to_be_visible()
                bounds=page.locator('#userNotificationMenu').bounding_box()
                self.assertGreaterEqual(bounds['x'],0)
                self.assertLessEqual(bounds['x']+bounds['width'],390)
                page.get_by_role('link',name='View All Notifications',exact=True).click()
                page.wait_for_url('**/notifications/')
                expect(page.locator('.notification-list li')).to_have_count(7)
                self.assertEqual(errors,[])
            finally:browser.close()
