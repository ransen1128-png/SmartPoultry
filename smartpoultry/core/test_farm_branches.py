from datetime import date
import importlib.util
import unittest

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import TestCase, override_settings

from core.models import Branch, Farm
from flocks.models import Flock


def create_farm(user, name='Original Farm'):
    return Farm.objects.create(owner=user,name=name,location='Argao',address='Original address',
        established_date=date(2026,1,1),contact_email='farm@example.invalid',contact_phone='09123456789')


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class FarmBranchesTests(TestCase):
    url='/farm/branches/'

    def setUp(self):
        self.user=get_user_model().objects.create_user('farm-owner',password='Strong-secret!79')
        self.farm=create_farm(self.user)
        self.client.force_login(self.user)

    def payload(self, **changes):
        return {'branch_name':'Branch One','address':'Branch address',
            'contact_number':'09123456789','description':'New branch','status':'active',**changes}

    def post(self, **changes):
        return self.client.post(self.url,self.payload(**changes),HTTP_ACCEPT='application/json')

    def test_original_farm_is_displayed_without_creating_branch(self):
        response=self.client.get(self.url)
        self.assertContains(response,'data-farm-row')
        self.assertContains(response,'Original address')
        self.assertNotContains(response,'data-main-branch-label')
        self.assertNotContains(response,'No branches yet')
        self.assertContains(response,'id="addBranchModal"')
        self.assertNotContains(response,'>Location</')
        self.assertNotContains(response,'name="location"')
        self.assertContains(response,'data-farm-information')
        self.assertContains(response,'id="farmBranchesTitle">Farm Information</h5>')
        self.assertNotContains(response,'<table')
        self.assertFalse(Branch.objects.exists())

    def test_first_and_subsequent_branches_preserve_original_farm_and_order(self):
        for name in ('Zulu Branch','Alpha Branch'):
            response=self.post(branch_name=name)
            self.assertEqual(response.status_code,200,response.content)
            self.assertEqual(response.json()['message'],'Branch added successfully!')
            self.assertTrue(response.json()['has_branches'])
            html=response.json()['html']
            self.assertIn('data-main-branch-label',html)
            self.assertLess(html.index('data-farm-row'),html.index('data-branch-id'))
        self.assertLess(html.index('Zulu Branch'),html.index('Alpha Branch'))
        self.assertEqual(Farm.objects.filter(owner=self.user).count(),1)
        self.assertEqual(Branch.objects.filter(farm=self.farm).count(),2)
        self.farm.refresh_from_db()
        self.assertEqual((self.farm.name,self.farm.address,self.farm.status),('Original Farm','Original address','active'))

    def test_required_fields_phone_status_and_duplicate_names(self):
        for changes in ({'branch_name':''},{'address':''},{'contact_number':''},
                {'contact_number':'123'},{'contact_number':'abcdefghijk'},{'status':'invalid'}):
            with self.subTest(changes=changes):
                self.assertEqual(self.post(**changes).status_code,400)
                self.assertFalse(Branch.objects.exists())
        self.assertEqual(self.post().status_code,200)
        self.assertEqual(self.post(branch_name='branch one').status_code,400)
        self.assertEqual(Branch.objects.count(),1)

    def test_search_covers_original_and_additional_addresses(self):
        self.post()
        response=self.client.get(self.url,{'q':'Original address'})
        self.assertContains(response,'data-farm-row')
        self.assertContains(response,'data-main-branch-label')
        self.assertNotContains(response,'data-branch-id=')
        response=self.client.get(self.url,{'q':'Branch address'})
        self.assertNotContains(response,'data-farm-row')
        self.assertContains(response,'Branch One')
        self.assertContains(self.client.get(self.url,{'q':'missing'}),'No farms or branches match your search.')

    def test_main_branch_name_is_reserved_for_original_farm(self):
        for name in ('Main Branch','main branch','MAIN BRANCH',' Main   Branch ','Main\tBranch'):
            with self.subTest(name=name):
                response=self.post(branch_name=name)
                self.assertEqual(response.status_code,400)
                self.assertIn('reserved for the original farm',response.json()['errors']['branch_name'][0]['message'])
                self.assertFalse(Branch.objects.filter(farm=self.farm).exists())
        self.assertEqual(self.post().status_code,200)
        branch=Branch.objects.get(farm=self.farm)
        self.assertEqual(self.post(branch_id=branch.pk,branch_name='Main Branch').status_code,400)
        branch.refresh_from_db()
        self.assertEqual(branch.name,'Branch One')
        self.farm.refresh_from_db()
        self.assertEqual(self.farm.name,'Original Farm')

    def test_owner_scope_and_cannot_delete_original_farm(self):
        other=get_user_model().objects.create_user('other-owner')
        foreign_farm=create_farm(other,'Private Farm')
        foreign=Branch.objects.create(farm=foreign_farm,name='Private branch')
        for action in ('save','delete'):
            response=self.post(action=action,branch_id=foreign.pk,farm=foreign_farm.pk)
            self.assertEqual(response.status_code,404)
        self.assertEqual(self.post(action='delete',branch_id='main').status_code,400)
        self.assertTrue(Farm.objects.filter(pk=self.farm.pk).exists())
        self.assertNotContains(self.client.get(self.url),'Private Farm')
        self.post(farm=foreign_farm.pk)
        self.assertEqual(Branch.objects.get(name='Branch One').farm_id,self.farm.pk)

    def test_edit_status_cascades_and_related_records_prevent_deletion(self):
        self.post()
        branch=Branch.objects.get(farm=self.farm)
        branch.location='Existing location';branch.save()
        flock=Flock.objects.create(user=self.user,branch=branch,flock_id='1',quantity=10,breed='layers')
        response=self.post(branch_id=branch.pk,branch_name='Renamed',status='inactive')
        self.assertEqual(response.status_code,200)
        flock.refresh_from_db();self.assertEqual(flock.status,'inactive')
        branch.refresh_from_db();self.assertEqual(branch.description,'New branch')
        self.assertEqual(branch.location,'Existing location')
        self.assertEqual(self.post(branch_id=branch.pk,action='delete').status_code,400)
        flock.refresh_from_db();self.assertEqual(flock.branch_id,branch.pk)
        self.assertTrue(Branch.objects.filter(pk=branch.pk).exists())

    def test_delete_empty_branch_restores_single_original_farm(self):
        self.post();branch=Branch.objects.get(farm=self.farm)
        response=self.post(branch_id=branch.pk,action='delete')
        self.assertEqual(response.status_code,200)
        self.assertIn('data-farm-row',response.json()['html'])
        self.assertNotIn('data-main-branch-label',response.json()['html'])
        self.assertFalse(Branch.objects.exists())

    def test_only_farm_information_is_shown_when_no_branches_even_with_old_search(self):
        response=self.client.get(self.url,{'q':'old branch'},HTTP_ACCEPT='application/json')
        self.assertFalse(response.json()['has_branches'])
        self.assertEqual(response.json()['query'],'')
        self.assertIn('Original Farm',response.json()['html'])
        self.assertNotIn('<table',response.json()['html'])

    def test_financial_records_are_not_detached_by_branch_deletion(self):
        from expenses.models import Expense
        self.post();branch=Branch.objects.get(farm=self.farm)
        expense=Expense.objects.create(user=self.user,branch=branch,date=date(2026,1,1),
            expense_type='other',description='Existing branch charge',amount=10)
        self.assertEqual(self.post(branch_id=branch.pk,action='delete').status_code,400)
        expense.refresh_from_db()
        self.assertEqual(expense.branch_id,branch.pk)

    def test_invalid_non_ajax_form_is_retained_for_correction(self):
        response=self.client.post(self.url,self.payload(contact_number='123'))
        self.assertContains(response,'value="Branch One"')
        self.assertContains(response,'data-modal-id="addBranchModal"')
        self.assertFalse(Branch.objects.exists())

    def test_escaped_content_and_non_ajax_fallback(self):
        response=self.client.post(self.url,self.payload(branch_name='<script>alert(1)</script>'))
        self.assertEqual(response.status_code,302)
        response=self.client.get(self.url)
        self.assertContains(response,'&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response,'<script>alert(1)</script>')


@unittest.skipUnless(importlib.util.find_spec('playwright'),'Desktop Playwright is not installed')
@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class FarmBranchesBrowserTests(StaticLiveServerTestCase):
    def test_create_cancel_edit_search_and_confirm_delete_without_navigation(self):
        from playwright.sync_api import sync_playwright, Error, expect
        user=get_user_model().objects.create_user('browser-farm',password='Strong-secret!79')
        farm=create_farm(user)
        self.client.force_login(user)
        session=self.client.cookies['sessionid'].value
        with sync_playwright() as playwright:
            try:browser=playwright.chromium.launch(channel='chrome',headless=True)
            except Error as error:raise unittest.SkipTest(str(error))
            try:
                page=browser.new_page();errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.context.add_cookies([{'name':'sessionid','value':session,'url':self.live_server_url}])
                page.goto(self.live_server_url+'/farm/branches/',wait_until='networkidle')
                page.evaluate('window.originalDocument=true')
                expect(page.locator('[data-farm-row]')).to_have_count(1)
                expect(page.locator('[data-main-branch-label]')).to_have_count(0)
                expect(page.locator('#farmBranchesTitle')).to_have_text('Farm Information')
                expect(page.locator('#branchSearchArea')).not_to_be_visible()
                expect(page.locator('#branchList table')).to_have_count(0)
                modal=page.locator('#addBranchModal')
                expect(modal).not_to_be_visible()
                expect(page.locator('#farmBranchesTitle')).to_have_text('Farm Information')
                page.get_by_role('button',name='Add Branch',exact=True).first.click()
                modal.get_by_role('button',name='Cancel',exact=True).click()
                expect(modal).not_to_be_visible()
                page.get_by_role('button',name='Add Branch',exact=True).first.click()
                modal.get_by_label('Branch Name',exact=True).fill('North Branch')
                modal.get_by_label('Address',exact=True).fill('North address')
                modal.get_by_label('Contact Number',exact=True).fill('09123456789')
                modal.get_by_role('button',name='Add Branch',exact=True).click()
                expect(page.locator('#appDialogTitle')).to_have_text('Branch added successfully!')
                page.locator('.sp-popup-ok').click()
                page.wait_for_function("!document.querySelector('#appDialog').open")
                expect(modal).not_to_be_visible()
                expect(page.locator('[data-main-branch-label]')).to_have_count(1)
                expect(page.locator('[data-branch-id]')).to_have_count(1)
                expect(page.locator('#farmBranchesTitle')).to_have_text('Farm Branches')
                expect(page.locator('#branchSearchArea')).to_be_visible()
                expect(page.locator('#branchList table')).to_have_count(1)
                self.assertTrue(page.evaluate('window.originalDocument'))
                page.get_by_role('button',name='Edit North Branch',exact=True).click()
                edit=page.locator('.modal.show')
                edit.get_by_label('Branch Name',exact=True).fill('Updated Branch')
                edit.get_by_role('button',name='Save Changes',exact=True).click()
                expect(page.locator('#appDialogTitle')).to_have_text('Branch updated successfully!')
                page.locator('.sp-popup-ok').click();page.wait_for_function("!document.querySelector('#appDialog').open")
                search=page.get_by_role('searchbox',name='Search farm and branches')
                search.fill('Original address');page.get_by_role('button',name='Search',exact=True).click()
                expect(page.locator('[data-branch-id]')).to_have_count(0)
                expect(page.locator('[data-farm-row]')).to_have_count(1)
                search.fill('');page.get_by_role('button',name='Search',exact=True).click()
                page.get_by_role('button',name='Delete Updated Branch',exact=True).click()
                page.locator('.sp-popup-cancel').click();page.wait_for_function("!document.querySelector('#appConfirmDialog').open")
                expect(page.locator('[data-branch-id]')).to_have_count(1)
                page.get_by_role('button',name='Delete Updated Branch',exact=True).click()
                page.locator('#appConfirmDialogConfirm').click()
                expect(page.locator('#appDialogTitle')).to_have_text('Branch deleted successfully!')
                page.locator('.sp-popup-ok').click();page.wait_for_function("!document.querySelector('#appDialog').open")
                expect(page.locator('[data-branch-id]')).to_have_count(0)
                expect(page.locator('[data-main-branch-label]')).to_have_count(0)
                expect(page.locator('#farmBranchesTitle')).to_have_text('Farm Information')
                expect(page.locator('#branchSearchArea')).not_to_be_visible()
                expect(page.locator('#branchList table')).to_have_count(0)
                page.set_viewport_size({'width':390,'height':844})
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                self.assertEqual(errors,[])
            finally:browser.close()
        self.assertEqual(Farm.objects.filter(owner=user).count(),1)
        self.assertFalse(Branch.objects.filter(farm=farm).exists())
