"""Selenium viewport and screenshot helpers for the local layout audits."""

import base64

from django.conf import settings


def open_owner_session(page, session, user):
    session['_auth_user_id'] = str(user.pk)
    session['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
    session['_auth_user_hash'] = user.get_session_auth_hash()
    session.save()
    page.goto('http://127.0.0.1:8000/login/')
    page.driver.add_cookie({'name': settings.SESSION_COOKIE_NAME, 'value': session.session_key, 'path': '/'})


def emulate_viewport(page, width, height, *, mobile=False):
    page.driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
        'width': width, 'height': height, 'mobile': mobile, 'deviceScaleFactor': 1,
    })
    page.driver.execute_cdp_cmd('Emulation.setTouchEmulationEnabled', {'enabled': mobile})


def capture_page(page, destination):
    driver = page.driver
    size = driver.execute_cdp_cmd('Page.getLayoutMetrics', {})['cssContentSize']
    screenshot = driver.execute_cdp_cmd('Page.captureScreenshot', {
        'format': 'png', 'captureBeyondViewport': True,
        'clip': {'x': 0, 'y': 0, 'width': size['width'], 'height': size['height'], 'scale': 1},
    })
    destination.write_bytes(base64.b64decode(screenshot['data']))
