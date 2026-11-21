import importlib.util
import unittest

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import TestCase, override_settings


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class LoginValidationTests(TestCase):
    def test_missing_fields_are_reported_individually(self):
        for data,email_error,password_error in [({},'Email required','Password required'),
                ({'email':'owner@example.invalid'},'','Password required'),({'password':'Secret!123'},'Email required','')]:
            with self.subTest(data=data):
                response=self.client.post('/login/',data)
                self.assertEqual(response.context['email_error'],email_error)
                self.assertEqual(response.context['password_error'],password_error)
                self.assertEqual(response.context['login_error'],'')
                self.assertNotIn('_auth_user_id',self.client.session)
                self.assertNotContains(response,'data-popup-message data-level="error"')

    def test_invalid_credentials_stay_generic_and_preserve_email_only(self):
        get_user_model().objects.create_user('owner','owner@example.invalid','Strong-secret!79')
        for email in ('owner@example.invalid','unknown@example.invalid'):
            response=self.client.post('/login/',{'email':email,'password':'wrong-private-password'})
            self.assertEqual(response.context['login_error'],'Incorrect Email and Password. Please try again')
            self.assertContains(response,f'value="{email}"')
            self.assertNotContains(response,'wrong-private-password')
            self.assertNotContains(response,'data-title="Login Failed!"')
            self.assertNotIn('_auth_user_id',self.client.session)


@unittest.skipUnless(importlib.util.find_spec('playwright'),'Desktop Playwright is not installed')
@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class LoginInlineBrowserTests(StaticLiveServerTestCase):
    def test_inline_errors_no_popups_and_valid_login_still_works(self):
        from playwright.sync_api import sync_playwright, Error, expect
        get_user_model().objects.create_user('inline-owner','inline@example.invalid','Strong-secret!79')
        with sync_playwright() as playwright:
            try:browser=playwright.chromium.launch(channel='chrome',headless=True)
            except Error as error:raise unittest.SkipTest(str(error))
            try:
                page=browser.new_page(viewport={'width':390,'height':844})
                errors=[];posts=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.on('request',lambda request:posts.append(request.url) if request.method=='POST' else None)
                page.goto(self.live_server_url+'/login/',wait_until='networkidle')
                login=page.get_by_role('button',name='Login',exact=True)
                login.click()
                expect(page.locator('#emailError')).to_have_text('Email required')
                expect(page.locator('#passwordError')).to_have_text('Password required')
                self.assertFalse(page.locator('#appDialog').evaluate('node=>node.open'))
                self.assertEqual(posts,[])
                page.locator('#email').fill('inline@example.invalid');login.click()
                expect(page.locator('#emailError')).not_to_be_visible()
                expect(page.locator('#passwordError')).to_have_text('Password required')
                page.locator('#password').fill('wrong-password')
                with page.expect_navigation(wait_until='networkidle'):login.click()
                expect(page.locator('#passwordError')).to_have_text('Incorrect Email and Password. Please try again')
                expect(page.locator('#passwordError')).to_be_visible()
                self.assertFalse(page.locator('#appDialog').evaluate('node=>node.open'))
                self.assertGreater(page.locator('#passwordError').bounding_box()['y'],page.locator('#password').bounding_box()['y'])
                page.locator('#password').fill('Strong-secret!79')
                expect(page.locator('#passwordError')).not_to_be_visible()
                with page.expect_navigation(wait_until='domcontentloaded'):login.click()
                self.assertTrue(page.url.endswith('/dashboard/'))
                expect(page.locator('#appDialogTitle')).to_have_text('Login Successful!')
                self.assertEqual(errors,[])
            finally:browser.close()
