"""Optional desktop Chrome checks against an isolated Django test database."""
import importlib.util
import re
import unittest

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings


@unittest.skipUnless(importlib.util.find_spec('playwright'), 'Desktop Playwright is not installed')
@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class LogoutBrowserTests(StaticLiveServerTestCase):
    def test_back_tabs_cached_restore_and_account_switch(self):
        from playwright.sync_api import sync_playwright, Error
        for name in ('first', 'second'):
            get_user_model().objects.create_user(name, name+'@example.invalid', 'Original-secret!79')
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(channel='chrome', headless=True,
                    ignore_default_args=['--disable-back-forward-cache'])
            except Error as error:
                raise unittest.SkipTest(str(error))
            try:
                context = browser.new_context()
                errors = []
                context.on('page', lambda tab: tab.on('pageerror', lambda error: errors.append(str(error))))
                page = context.new_page()
                login_pattern = re.compile(r'/login/(?:\?.*)?$')

                def login(name):
                    page.goto(self.live_server_url+'/login/', wait_until='domcontentloaded')
                    page.locator('#email').fill(name+'@example.invalid')
                    page.locator('#password').fill('Original-secret!79')
                    with page.expect_navigation(wait_until='domcontentloaded'):
                        page.get_by_role('button', name='Login', exact=True).click()
                    page.locator('#appDialog .sp-popup-ok').click()

                login('first')
                page.goto(self.live_server_url+'/farm/branches/', wait_until='domcontentloaded')
                page.goto(self.live_server_url+'/profile/', wait_until='networkidle')
                other = context.new_page()
                other.goto(self.live_server_url+'/profile/', wait_until='networkidle')
                page.bring_to_front()
                page.locator('#accountDropdown').click()
                page.locator('a[href="/logout/"]').last.click()
                page.locator('#appConfirmDialogConfirm').click()
                page.wait_for_url(login_pattern, wait_until='domcontentloaded')
                other.wait_for_url(login_pattern, wait_until='domcontentloaded')
                self.assertEqual(other.locator('body[data-owner]').count(), 0)
                for direction in ('back', 'forward', 'back'):
                    with page.expect_event('framenavigated', predicate=lambda frame: frame == page.main_frame):
                        page.evaluate(f'history.{direction}()')
                    page.wait_for_function("location.pathname === '/login/' && !document.body.hasAttribute('data-owner')")
                    self.assertEqual(page.locator('body[data-owner]').count(), 0)

                login('first')
                page.goto(self.live_server_url+'/profile/', wait_until='networkidle')
                page.evaluate("window.dispatchEvent(new PageTransitionEvent('pagehide', {persisted:true}))")
                self.assertIsNotNone(page.locator('html').get_attribute('data-session-checking'))
                context.request.get(self.live_server_url+'/logout/')
                page.evaluate("window.dispatchEvent(new PageTransitionEvent('pageshow', {persisted:true}))")
                page.wait_for_url(login_pattern, wait_until='domcontentloaded')
                self.assertEqual(page.locator('body[data-owner]').count(), 0)

                login('second')
                response = page.goto(self.live_server_url+'/farm/branches/', wait_until='networkidle')
                self.assertIn('no-store', response.headers['cache-control'])
                self.assertIn('second', page.locator('.topbar-user').inner_text())
                self.assertNotIn('first', page.locator('.topbar-user').inner_text())
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def test_history_entry_saved_before_the_logout_fix(self):
        from playwright.sync_api import sync_playwright, Error
        get_user_model().objects.create_user('legacy-history', 'legacy@example.invalid', 'Original-secret!79')
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(channel='chrome', headless=True,
                    ignore_default_args=['--disable-back-forward-cache'])
            except Error as error:
                raise unittest.SkipTest(str(error))
            try:
                page = browser.new_page()
                console_messages = []
                page.on('console', lambda message: console_messages.append(message.text) if 'Clear-Site-Data' in message.text else None)
                page.goto(self.live_server_url+'/login/', wait_until='domcontentloaded')
                page.locator('#email').fill('legacy@example.invalid')
                page.locator('#password').fill('Original-secret!79')
                with page.expect_navigation(wait_until='domcontentloaded'):
                    page.get_by_role('button', name='Login', exact=True).click()
                page.locator('#appDialog .sp-popup-ok').click()

                def legacy_page(route):
                    response = route.fetch()
                    headers = {key: value for key, value in response.headers.items()
                        if key.lower() not in ('cache-control','expires','pragma','content-length')}
                    html = re.sub(r'<script[^>]*auth_session\.js[^>]*></script>', '', response.text())
                    route.fulfill(status=response.status, headers=headers, body=html)

                page.route('**/farm/branches/', legacy_page)
                page.goto(self.live_server_url+'/farm/branches/', wait_until='networkidle')
                self.assertEqual(page.locator('script[src*="auth_session.js"]').count(), 0)
                page.unroute('**/farm/branches/', legacy_page)
                if page.locator('#appDialog').evaluate('(node)=>node.open'):
                    page.locator('#appDialog .sp-popup-ok').click()
                    page.wait_for_function("!document.querySelector('#appDialog').open")
                page.locator('#accountDropdown').click()
                page.locator('a[href="/logout/"]').last.click()
                pattern = re.compile(r'/login/(?:\?.*)?$')
                page.wait_for_url(pattern, wait_until='domcontentloaded')
                for direction in ('back', 'forward', 'back'):
                    with page.expect_event('framenavigated', predicate=lambda frame: frame == page.main_frame):
                        page.evaluate(f'history.{direction}()')
                    # A real bfcache restore doesn't fire DOMContentLoaded again.
                    try:
                        page.wait_for_function("location.pathname === '/login/' && !document.body.hasAttribute('data-owner')", timeout=5000)
                    except Error as error:
                        raise AssertionError(f'History {direction}: url={page.url}, account_page={page.locator("body[data-owner]").count()}, secure={page.evaluate("isSecureContext")}, console={console_messages}') from error
                    self.assertEqual(page.locator('body[data-owner]').count(), 0)
            finally:
                browser.close()
