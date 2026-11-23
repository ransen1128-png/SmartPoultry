"""Browser startup shared by the numbered automation cases."""

from getpass import getpass
import os
from pathlib import Path
import sys
from unittest import SkipTest

from playwright.sync_api import expect


def expect_field_error(field):
    message = field.evaluate('field => field.validationMessage')
    expect(field).to_have_attribute('aria-invalid', 'true')
    ids = (field.get_attribute('aria-describedby') or '').split()
    alerts = field.page.locator('[data-sp-field-error]').filter(has_text=message)
    expect(alerts.and_(field.page.locator(', '.join(f'#{value}' for value in ids)))).to_be_visible()


def launch_browser(playwright):
    channel = os.environ.get('SMARTPOULTRY_BROWSER_CHANNEL')
    if channel:
        return playwright.chromium.launch(channel=channel, headless=True)
    if not Path(playwright.chromium.executable_path).is_file():
        raise RuntimeError(
            'Install Chromium with "python -m playwright install chromium", '
            'or set SMARTPOULTRY_BROWSER_CHANNEL to an installed Chrome or Edge channel.'
        )
    return playwright.chromium.launch(headless=True)


def live_base_url():
    return os.environ.get('SMARTPOULTRY_TEST_BASE_URL', 'https://smartpoultry-l3qo.onrender.com').rstrip('/')


def read_test_value(variable, prompt, *, secret=False):
    value = os.environ.get(variable)
    if value:
        return value
    if not sys.stdin.isatty():
        raise SkipTest(f'Set {variable} to run this case without an interactive terminal.')
    try:
        value = (getpass if secret else input)(prompt)
    except EOFError:
        raise SkipTest(f'Set {variable} to run this case without an interactive terminal.') from None
    if not value:
        raise SkipTest(f'Provide a value for {variable} to run this case.')
    return value
