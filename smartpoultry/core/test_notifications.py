"""Notification integration checks; no production records or API credentials."""
import importlib.util
from pathlib import Path
import unittest

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.template.loader import render_to_string
from django.test import TestCase, override_settings


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class NotificationMessageTests(TestCase):
    def test_success_is_only_queued_after_valid_login(self):
        get_user_model().objects.create_user('popup-owner', 'popup@example.invalid', 'Strong-secret!79')
        response = self.client.post('/login/', {'email':'popup@example.invalid','password':'wrong'})
        self.assertContains(response, 'data-title="Login Failed!"')
        self.assertNotIn('_auth_user_id', self.client.session)
        response = self.client.post('/login/', {'email':'popup@example.invalid','password':'Strong-secret!79'}, follow=True)
        self.assertContains(response, 'data-title="Login Successful!"')
        self.assertIn('_auth_user_id', self.client.session)
        self.assertNotContains(self.client.get('/dashboard/'), 'data-title="Login Successful!"')

    def test_untrusted_message_is_escaped(self):
        html = render_to_string('includes/notifications.html', {'error':'<script>alert("private")</script>'})
        self.assertNotIn('<script>alert(', html)
        self.assertIn('&lt;script&gt;', html)


@unittest.skipUnless(importlib.util.find_spec('playwright'), 'Desktop Playwright is not installed')
class NotificationBrowserTests(unittest.TestCase):
    def setUp(self):
        from playwright.sync_api import sync_playwright, Error
        self.playwright = sync_playwright().start()
        try:
            self.browser = self.playwright.chromium.launch(channel='chrome', headless=True)
        except Error as error:
            self.playwright.stop()
            self.skipTest(str(error))
        self.addCleanup(self.playwright.stop)
        self.addCleanup(self.browser.close)
        self.page = self.browser.new_page()
        self.errors = []
        self.page.on('pageerror', lambda error:self.errors.append(str(error)))
        template = render_to_string('includes/notifications.html')
        root = Path(__file__).resolve().parents[1]
        script = (root/'static/js/notifications.js').read_text(encoding='utf-8')
        css = (root/'static/css/notifications.css').read_text(encoding='utf-8')
        html = f'''<html><head><meta charset="UTF-8"></head><body data-owner="test"><form method="post"><input name="name" required><button type="submit">Save</button></form>
            {template}<style>{css}</style><script>{script}</script></body></html>'''
        self.page.route('https://popup.test/', lambda route:route.fulfill(body=html, content_type='text/html'))
        self.page.route('**/static/**', lambda route:route.fulfill(body='', content_type='text/plain'))
        self.page.goto('https://popup.test/')

    def tearDown(self):
        self.assertEqual(self.errors, [])

    def test_confirmation_cancel_and_confirm_callbacks(self):
        self.page.evaluate("window.accepted=0;void showAppConfirmDialog('Delete this record?',()=>window.accepted++)")
        self.page.locator('.sp-popup-cancel').click()
        self.page.wait_for_function("!document.querySelector('#appConfirmDialog').open")
        self.assertEqual(self.page.evaluate('window.accepted'),0)
        self.page.evaluate("void showAppConfirmDialog('Delete this record?',()=>window.accepted++)")
        self.page.locator('#appConfirmDialogConfirm').click()
        self.page.wait_for_function('window.accepted===1')

    def test_invalid_fields_warn_without_submitting(self):
        self.page.get_by_role('button',name='Save',exact=True).click()
        self.assertEqual(self.page.locator('#appDialogTitle').inner_text(),'Please Complete All Required Fields!')
        self.assertEqual(self.page.url,'https://popup.test/')

    def test_deduplicate_writes_and_success_popups(self):
        requests=[]
        def saved(route):
            requests.append(route.request.method)
            route.fulfill(status=201,json={'id':1})
        self.page.route('**/api/items/',saved)
        self.page.evaluate("Promise.all([fetch('/api/items/',{method:'POST',body:'{}'}),fetch('/api/items/',{method:'POST',body:'{}'})])")
        self.page.wait_for_function("document.querySelector('#appDialog').open")
        self.assertEqual(requests,['POST'])
        self.assertEqual(self.page.locator('#appDialog .sp-popup-icon').inner_text(),'\u2713')
        self.assertEqual(self.page.locator('#appDialogTitle').inner_text(),'Successfully Added!')
        self.page.locator('.sp-popup-ok').click()
        self.page.wait_for_function("!document.querySelector('#appDialog').open")

    def test_server_failure_is_not_success_and_does_not_leak(self):
        self.page.route('**/api/items/',lambda route:route.fulfill(status=500,body='<html>Traceback SECRET_KEY=private</html>',content_type='text/html'))
        self.page.evaluate("fetch('/api/items/',{method:'POST',body:'{}'})")
        self.assertEqual(self.page.locator('#appDialog').get_attribute('data-type'),'error')
        self.assertNotIn('SECRET_KEY',self.page.locator('#appDialogText').inner_text())
        self.assertNotIn('Successfully',self.page.locator('#appDialogTitle').inner_text())

    def test_success_survives_navigation_once(self):
        self.page.route('**/api/items/',lambda route:route.fulfill(status=201,json={'id':1}))
        self.page.evaluate("fetch('/api/items/',{method:'POST',body:'{}'}).then(()=>location.reload())")
        self.page.wait_for_function("document.querySelector('#appDialog')?.open")
        self.assertEqual(self.page.locator('#appDialogTitle').inner_text(),'Successfully Added!')
        self.page.locator('.sp-popup-ok').click()
        self.page.wait_for_function("!document.querySelector('#appDialog').open")
        self.page.reload()
        self.assertFalse(self.page.locator('#appDialog').evaluate('(node)=>node.open'))

    def test_mobile_popup_fits_viewport_and_escapes_markup(self):
        self.page.set_viewport_size({'width':360,'height':740})
        self.page.evaluate("void SmartPoultry.notify({type:'error',message:'<img src=x onerror=alert(1)>'})")
        bounds=self.page.locator('#appDialog').bounding_box()
        self.assertGreaterEqual(bounds['x'],0)
        self.assertLessEqual(bounds['x']+bounds['width'],360)
        self.assertEqual(self.page.locator('#appDialog img').count(),0)

    def test_network_failure_has_no_success_notice(self):
        self.page.route('**/api/items/',lambda route:route.abort('failed'))
        self.page.evaluate("fetch('/api/items/',{method:'POST'}).catch(()=>{})")
        self.assertEqual(self.page.locator('#appDialogTitle').inner_text(),'Connection Error!')

    def test_native_submit_preserves_action_and_blocks_repeat(self):
        requests=[]
        self.page.route('**/save/',lambda route:(requests.append(route.request.post_data),route.fulfill(body='Saved')))
        self.page.locator('form').evaluate("form=>{form.action='/save/';form.querySelector('button').name='action';form.querySelector('button').value='save';form.querySelector('input').value='Feed';}")
        self.page.get_by_role('button',name='Save',exact=True).click()
        self.page.wait_for_url('**/save/')
        self.assertEqual(requests,['name=Feed&action=save'])

    def test_queued_or_invalid_responses_are_not_reported_as_saved(self):
        for status,body,content_type in [(202,'{"queued":true}','application/json'),
                (200,'<html>Unexpected page</html>','text/html'),(200,'not json','application/json')]:
            with self.subTest(status=status,body=body):
                self.page.reload()
                self.page.route('**/api/pending/',lambda route,request,s=status,b=body,c=content_type:route.fulfill(status=s,body=b,content_type=c))
                self.page.evaluate("fetch('/api/pending/',{method:'POST'})")
                self.assertNotEqual(self.page.locator('#appDialog').get_attribute('data-type'),'success')

    def test_delete_without_response_body_is_confirmed(self):
        self.page.route('**/api/items/1/',lambda route:route.fulfill(status=204,body=''))
        self.page.evaluate("fetch('/api/items/1/',{method:'DELETE'})")
        self.page.wait_for_function("document.querySelector('#appDialog').open")
        self.assertEqual(self.page.locator('#appDialogTitle').inner_text(),'Successfully Deleted!')


@unittest.skipUnless(importlib.util.find_spec('playwright'), 'Desktop Playwright is not installed')
@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class InventoryPopupBrowserTests(StaticLiveServerTestCase):
    def test_distribution_cancel_reopen_confirm_all_and_stock_warning(self):
        from datetime import date
        from core.models import Farm, Branch
        from flocks.models import Flock
        from inventory.models import Inventory, InventoryDistribution
        from playwright.sync_api import sync_playwright, Error
        user=get_user_model().objects.create_user('popup-stock', 'stock@example.invalid','Strong-secret!79')
        farm=Farm.objects.create(owner=user,name='Test Farm',location='Town',established_date=date(2026,1,1),contact_email='stock@example.invalid',contact_phone='123')
        branch=Branch.objects.create(farm=farm,name='North')
        Flock.objects.create(user=user,branch=branch,flock_id='1',breed='other',quantity=10)
        item=Inventory.objects.create(user=user,item_type='feed',name='Popup feed',quantity=5,unit='sacks',package_size=25,content_unit='kg',cost_per_unit=20)
        self.client.force_login(user)
        session=self.client.cookies['sessionid'].value
        with sync_playwright() as playwright:
            try: browser=playwright.chromium.launch(channel='chrome',headless=True)
            except Error as error: raise unittest.SkipTest(str(error))
            try:
                page=browser.new_page()
                errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.context.add_cookies([{'name':'sessionid','value':session,'url':self.live_server_url}])
                page.context.request.get(self.live_server_url+'/profile/')
                page.goto(self.live_server_url+'/inventory/',wait_until='networkidle')
                page.get_by_role('button',name='Distribute',exact=True).first.click()
                page.locator('#distributionModal [data-bs-dismiss=modal]').first.click()
                page.wait_for_function("!document.querySelector('#distributionModal').classList.contains('show')")
                page.get_by_role('button',name='Distribute',exact=True).first.click()
                page.locator('#distributionBranch').select_option(str(branch.pk))
                page.locator('#distributionQuantity').fill('5')
                page.locator('#distributionModal [data-bs-dismiss=modal]').first.click()
                page.locator('.sp-popup-cancel').click()
                page.wait_for_function("!document.querySelector('#appConfirmDialog').open")
                self.assertEqual(page.locator('#distributionQuantity').input_value(),'5')
                page.locator('#saveDistributionBtn').click()
                page.locator('#appConfirmDialogConfirm').click()
                page.wait_for_function("document.querySelector('#appDialog').open")
                self.assertIn('Successfully',page.locator('#appDialogTitle').inner_text(),page.locator('#appDialogText').inner_text())
                page.locator('.sp-popup-ok').click()
                page.wait_for_function("document.querySelector('#appDialogTitle').textContent.includes('Out of stock')")
                self.assertIn('Popup feed',page.locator('#appDialogText').inner_text())
                self.assertEqual(errors,[])
            finally: browser.close()
        item.refresh_from_db()
        self.assertEqual(item.quantity,0)
        self.assertEqual(InventoryDistribution.objects.filter(inventory=item).count(),1)
