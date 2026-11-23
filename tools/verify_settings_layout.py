"""Inspect the local Settings UI in an isolated Chrome session."""

import json
import os
from pathlib import Path
import sys

try:
    from tools.automation_browser import expect, launch_browser
    from tools.selenium_audit import capture_page, emulate_viewport, open_owner_session
except ModuleNotFoundError:
    from automation_browser import expect, launch_browser
    from selenium_audit import capture_page, emulate_viewport, open_owner_session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'smartpoultry'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django

django.setup()

from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore



def main():
    session = SessionStore()
    browser = launch_browser()
    out = ROOT / '.postgres-migration/settings-preview'
    out.mkdir(parents=True, exist_ok=True)
    try:
        page = browser.new_page()
        emulate_viewport(page, 1507, 940)
        open_owner_session(page, session, get_user_model().objects.get(pk=3))
        page.goto('http://127.0.0.1:8000/settings/')
        expect(page.locator('#notifications-panel')).to_be_visible()
        style = page.locator('.settings-layout').evaluate('element => getComputedStyle(element).display')
        assert style == 'grid', style
        nav = page.locator('.settings-navigation').element_handle().rect
        panel = page.locator('#notifications-panel').element_handle().rect
        assert panel['x'] > nav['x'] + nav['width']
        for item in page.locator('.settings-switch').elements():
            assert item.rect['x'] > panel['x'] + panel['width'] * .8
        capture_page(page, out / 'notifications.png')

        page.locator('#security-tab').click()
        expect(page.locator('#security-panel')).to_be_visible()
        for label in ('current_password', 'new_password', 'confirm_password'):
            field = page.locator(f'#{label}')
            button = page.locator(f'[data-password-target="{label}"]')
            button.click()
            expect(field).to_have_attribute('type', 'text')
            button.click()
            expect(field).to_have_attribute('type', 'password')
        capture_page(page, out / 'security.png')
        emulate_viewport(page, 500, 900)
        capture_page(page, out / 'security-mobile.png')
        columns = page.locator('.settings-password-row').first.evaluate(
            'element => getComputedStyle(element).gridTemplateColumns',
        )
        assert len(columns.split()) == 1
    finally:
        try:
            browser.close()
        finally:
            if session.session_key:
                session.delete()
    print(json.dumps({'layout': 'grid', 'notifications': 'right-aligned switches',
                      'security': 'visible and working toggles', 'screenshots': str(out)}, indent=2))


if __name__ == '__main__':
    main()
