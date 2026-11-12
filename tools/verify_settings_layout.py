"""Inspect the real Settings UI in an isolated Chrome session."""
import os,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'smartpoultry'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settings')
import django
django.setup()
from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from playwright.sync_api import sync_playwright

user=get_user_model().objects.get(pk=3)
session=SessionStore()
session['_auth_user_id']=str(user.pk)
session['_auth_user_backend']='django.contrib.auth.backends.ModelBackend'
session['_auth_user_hash']=user.get_session_auth_hash()
session.save()
out=ROOT/'.postgres-migration/settings-preview';out.mkdir(exist_ok=True)
try:
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(channel='chrome',headless=True)
        context=browser.new_context(viewport={'width':1507,'height':940},device_scale_factor=1)
        context.add_cookies([{'name':'sessionid','value':session.session_key,'url':'http://127.0.0.1:8000'}])
        page=context.new_page()
        page.goto('http://127.0.0.1:8000/settings/',wait_until='networkidle')
        page.locator('#notifications-panel').wait_for(state='visible')
        style=page.locator('.settings-layout').evaluate('(element)=>getComputedStyle(element).display')
        assert style=='grid',style
        nav=page.locator('.settings-navigation').bounding_box()
        panel=page.locator('#notifications-panel').bounding_box()
        assert panel['x']>nav['x']+nav['width']
        for item in page.locator('.settings-switch').all():
            box=item.bounding_box();assert box['x']>panel['x']+panel['width']*.8
        page.screenshot(path=str(out/'notifications.png'),full_page=True)
        page.locator('#security-tab').click()
        page.locator('#security-panel').wait_for(state='visible')
        for label in ['current_password','new_password','confirm_password']:
            field=page.locator('#'+label)
            button=page.locator('[data-password-target='+label+']')
            button.click();assert field.get_attribute('type')=='text'
            button.click();assert field.get_attribute('type')=='password'
        page.screenshot(path=str(out/'security.png'),full_page=True)
        page.set_viewport_size({'width':500,'height':900})
        page.screenshot(path=str(out/'security-mobile.png'),full_page=True)
        assert page.locator('.settings-password-row').first.evaluate('(e)=>getComputedStyle(e).gridTemplateColumns').split().__len__()==1
        browser.close()
    print(json.dumps({'layout':'grid','notifications':'right-aligned switches','security':'visible and working toggles','screenshots':str(out)},indent=2))
finally:
    session.delete()
