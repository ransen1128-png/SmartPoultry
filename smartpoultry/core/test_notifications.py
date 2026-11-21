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
    def test_login_redirects_without_a_success_popup(self):
        get_user_model().objects.create_user('popup-owner', 'popup@example.invalid', 'Strong-secret!79')
        response = self.client.post('/login/', {'email':'popup@example.invalid','password':'wrong'})
        self.assertContains(response, 'Incorrect email or password. Please try again.')
        self.assertNotContains(response, 'data-title="Login Failed!"')
        self.assertNotIn('_auth_user_id', self.client.session)
        response = self.client.post('/login/', {'email':'popup@example.invalid','password':'Strong-secret!79'}, follow=True)
        self.assertRedirects(response, '/dashboard/')
        self.assertNotContains(response, 'Login Successful!')
        self.assertIn('_auth_user_id', self.client.session)

    def test_untrusted_message_is_escaped(self):
        html = render_to_string('includes/notifications.html', {'error':'<script>alert("private")</script>'})
        self.assertNotIn('<script>alert(', html)
        self.assertIn('&lt;script&gt;', html)

    def test_settings_password_mismatch_is_inline(self):
        user = get_user_model().objects.create_user('settings-owner', password='Original!79')
        self.client.force_login(user)
        response = self.client.post('/settings/', {
            'action': 'password',
            'current_password': 'Original!79',
            'new_password': 'Replacement!79',
            'confirm_password': 'Different!79',
        })
        self.assertContains(response, 'aria-describedby="confirmPasswordError"')
        self.assertContains(response, 'New passwords do not match.', count=1)
        self.assertNotContains(response, 'data-popup-message')
        user.refresh_from_db()
        self.assertTrue(user.check_password('Original!79'))


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
        self.assertEqual(self.page.locator('form .sp-field-error').count(),1)
        self.assertEqual(self.page.locator('[name=name]').get_attribute('aria-invalid'),'true')
        self.assertFalse(self.page.locator('#appDialog').evaluate('node=>node.open'))
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
        self.assertEqual(self.page.locator('.sp-inline-message').get_attribute('data-type'),'error')
        self.assertNotIn('SECRET_KEY',self.page.locator('.sp-inline-message').inner_text())
        self.assertFalse(self.page.locator('#appDialog').evaluate('node=>node.open'))

    def test_success_survives_navigation_once(self):
        self.page.route('**/api/items/',lambda route:route.fulfill(status=201,json={'id':1}))
        self.page.evaluate("fetch('/api/items/',{method:'POST',body:'{}'}).then(()=>location.reload())")
        self.page.wait_for_function("document.querySelector('#appDialog')?.open")
        self.assertEqual(self.page.locator('#appDialogTitle').inner_text(),'Successfully Added!')
        self.page.locator('.sp-popup-ok').click()
        self.page.wait_for_function("!document.querySelector('#appDialog').open")
        self.page.reload()
        self.assertFalse(self.page.locator('#appDialog').evaluate('(node)=>node.open'))

    def test_mobile_inline_error_fits_viewport_and_escapes_markup(self):
        self.page.set_viewport_size({'width':360,'height':740})
        self.page.evaluate("void SmartPoultry.notify({type:'error',message:'<img src=x onerror=alert(1)>'})")
        bounds=self.page.locator('.sp-inline-message').bounding_box()
        self.assertGreaterEqual(bounds['x'],0)
        self.assertLessEqual(bounds['x']+bounds['width'],360)
        self.assertEqual(self.page.locator('.sp-inline-message img').count(),0)
        self.assertFalse(self.page.locator('#appDialog').evaluate('node=>node.open'))

    def test_network_failure_has_no_success_notice(self):
        self.page.route('**/api/items/',lambda route:route.abort('failed'))
        self.page.evaluate("fetch('/api/items/',{method:'POST'}).catch(()=>{})")
        self.assertIn('Connection Error!',self.page.locator('.sp-inline-message').inner_text())
        self.assertFalse(self.page.locator('#appDialog').evaluate('node=>node.open'))

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

    def test_api_field_errors_appear_below_input_and_clear_when_edited(self):
        self.page.route('**/api/items/',lambda route:route.fulfill(status=400,json={'name':['This name already exists.']}))
        self.page.evaluate("fetch('/api/items/',{method:'POST',body:'{}'})")
        self.assertEqual(self.page.locator('form .sp-field-error').inner_text(),'This name already exists.')
        self.assertEqual(self.page.locator('[name=name]').get_attribute('aria-invalid'),'true')
        self.assertFalse(self.page.locator('#appDialog').evaluate('node=>node.open'))
        self.page.locator('[name=name]').fill('New item')
        self.assertEqual(self.page.locator('.sp-field-error').count(),0)
        self.assertIsNone(self.page.locator('[name=name]').get_attribute('aria-invalid'))

    def test_django_error_message_is_inline_and_success_remains_popup(self):
        self.page.evaluate("""() => {
            const message=document.createElement('span');message.dataset.popupMessage='';
            message.dataset.level='error';message.textContent='Unable to save this record.';
            document.body.append(message);document.dispatchEvent(new Event('DOMContentLoaded'));
        }""")
        self.assertIn('Unable to save this record.',self.page.locator('.sp-inline-message').inner_text())
        self.assertFalse(self.page.locator('#appDialog').evaluate('node=>node.open'))
        self.page.evaluate("void SmartPoultry.notify({type:'success',message:'Changes saved successfully.'})")
        self.assertTrue(self.page.locator('#appDialog').evaluate('node=>node.open'))

    def test_legacy_error_with_saved_word_is_not_a_success_popup(self):
        self.page.evaluate("void showAppDialog('This record cannot be saved.', 'Record')")
        self.assertFalse(self.page.locator('#appDialog').evaluate('node=>node.open'))
        self.assertIn('This record cannot be saved.',self.page.locator('.sp-inline-message').inner_text())

    def test_error_is_visible_when_editing_form_is_hidden_in_history_modal(self):
        self.page.evaluate("""() => {
            document.querySelector('form').hidden=true;
            const modal=document.createElement('div');modal.className='modal show';
            modal.innerHTML='<div class="modal-body"><section hidden><form><input name="name"></form></section></div>';
            document.body.append(modal);
        }""")
        self.page.route('**/api/items/',lambda route:route.fulfill(status=400,json={'name':['This record cannot be changed.']}))
        self.page.evaluate("fetch('/api/items/',{method:'POST',body:'{}'})")
        node=self.page.locator('.modal-body > .sp-inline-message')
        self.assertTrue(node.is_visible())
        self.assertIn('This record cannot be changed.',node.inner_text())
        self.assertFalse(self.page.locator('#appDialog').evaluate('node=>node.open'))


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
        empty_branch=Branch.objects.create(farm=farm,name='Empty branch')
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
                page.wait_for_function("bootstrap.Modal.getInstance(document.querySelector('#distributionModal'))?._isTransitioning === false")
                page.locator('#distributionModal [data-bs-dismiss=modal]').first.click()
                page.wait_for_function("!document.querySelector('#distributionModal').classList.contains('show')")
                page.get_by_role('button',name='Distribute',exact=True).first.click()
                page.locator('#distributionBranch').select_option(str(branch.pk))
                page.locator('#distributionQuantity').fill('6')
                page.locator('#saveDistributionBtn').click()
                self.assertFalse(page.locator('#appDialog').evaluate('node=>node.open'))
                self.assertEqual(page.locator('#distributionQuantity').input_value(),'6')
                page.locator('#distributionBranch').select_option(str(empty_branch.pk))
                page.locator('#distributionQuantity').fill('1')
                page.locator('#saveDistributionBtn').click()
                page.wait_for_function("document.querySelector('#distributionFeedback').textContent.includes('Empty branch')")
                self.assertFalse(page.locator('#appDialog').evaluate('node=>node.open'))
                self.assertTrue(page.locator('#distributionModal').evaluate("node=>node.classList.contains('show')"))
                self.assertEqual(page.locator('#distributionQuantity').input_value(),'1')
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
                page.wait_for_function("[...document.querySelectorAll('.sp-inline-message')].some(node=>node.textContent.includes('Out of stock'))")
                self.assertIn('Popup feed',page.locator('#distributionModal .sp-inline-message').inner_text())
                page.wait_for_function("!document.querySelector('#appDialog').open")
                self.assertEqual(errors,[])
            finally: browser.close()
        item.refresh_from_db()
        self.assertEqual(item.quantity,0)
        self.assertEqual(InventoryDistribution.objects.filter(inventory=item).count(),1)
