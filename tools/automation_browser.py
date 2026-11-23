"""Browser startup shared by the numbered automation cases."""

from getpass import getpass
import os
import sys
from unittest import SkipTest

try:
    from tools.selenium_browser import expect, launch_browser
except ModuleNotFoundError:
    from selenium_browser import expect, launch_browser



def expect_field_error(field):
    message = field.evaluate('field => field.validationMessage')
    expect(field).to_have_attribute('aria-invalid', 'true')
    ids = (field.get_attribute('aria-describedby') or '').split()
    alerts = field.page.locator('[data-sp-field-error]').filter(has_text=message)
    expect(alerts.and_(field.page.locator(', '.join(f'#{value}' for value in ids)))).to_be_visible()


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
