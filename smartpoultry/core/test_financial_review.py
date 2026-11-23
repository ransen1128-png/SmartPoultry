from datetime import timedelta
from decimal import Decimal
import re
from pathlib import Path
import unittest

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.template.loader import render_to_string
from django.test import TestCase, SimpleTestCase, override_settings
from django.utils import timezone

from core.models import Farm, Branch
from flocks.models import Flock
from production.models import MortalityRecord
from revenue.models import Revenue


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class FinancialReviewTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username='financial-owner')
        self.client.force_login(self.owner)
        self.today = timezone.localdate()

    def sale(self, owner, kind, amount, day):
        return Revenue.objects.create(user=owner, revenue_type=kind, quantity=1,
            unit='pcs', price_per_unit=amount, date=day)

    def test_egg_scenario_baseline_excludes_other_products_owners_and_future_months(self):
        self.sale(self.owner, 'eggs', 32, self.today)
        self.sale(self.owner, 'birds', 300, self.today)
        next_month = (self.today.replace(day=28) + timedelta(days=4)).replace(day=1)
        self.sale(self.owner, 'eggs', 999, next_month)
        other = get_user_model().objects.create_user(username='financial-other')
        self.sale(other, 'eggs', 500, self.today)
        result = self.client.get('/scenario-analysis/')
        self.assertEqual(result.context['scenario_metrics']['revenue'], Decimal('332'))
        self.assertEqual(result.context['scenario_metrics']['egg_revenue'], Decimal('32'))
        self.assertContains(result, 'data-base-egg-revenue="32.00"')

    def test_mortality_uses_pre_death_population_and_branch_scope(self):
        farm = Farm.objects.create(owner=self.owner, name='Farm', established_date=self.today,
            contact_email='farm@example.com', contact_phone='09123456789')
        branch = Branch.objects.create(farm=farm, name='A')
        flock = Flock.objects.create(user=self.owner, branch=branch, flock_id='01', breed='layers', quantity=50)
        MortalityRecord.objects.create(user=self.owner, branch=branch, flock=flock, quantity=3, date=self.today)
        flock.refresh_from_db()
        self.assertEqual(flock.quantity, 47)
        for params in ({}, {'branch': branch.pk}):
            result = self.client.get('/dashboard/', params)
            self.assertEqual(result.context['metrics']['mortality_rate'], 6)
        result = self.client.get('/dashboard/', {'month':self.today.month, 'year':self.today.year})
        self.assertContains(result, 'current live chickens + those deaths')

    def test_empty_population_has_zero_mortality(self):
        self.assertEqual(self.client.get('/dashboard/').context['metrics']['mortality_rate'], 0)

    def test_staff_view_link_requires_matching_django_admin_permission(self):
        staff = get_user_model().objects.create_user(username='financial-staff', is_staff=True)
        self.client.force_login(staff)
        url = f'/admin/accounts/userprofile/{self.owner.pk}/change/'
        self.assertNotContains(self.client.get('/admin-dashboard/'), f'href="{url}"')
        self.assertEqual(self.client.get(url).status_code, 403)
        staff.user_permissions.add(Permission.objects.get(codename='view_userprofile', content_type__app_label='accounts'))
        self.assertContains(self.client.get('/admin-dashboard/'), f'href="{url}"')
        self.assertEqual(self.client.get(url).status_code, 200)


class ScenarioCalculationBrowserTests(SimpleTestCase):
    def test_egg_only_adjustment_and_strict_inline_percentage_validation(self):
        from playwright.sync_api import sync_playwright, Error
        html = render_to_string('scenario_analysis.html', {'scenario_metrics':{
            'revenue':332, 'egg_revenue':32, 'expenses':20, 'feed_cost':10, 'profit':312}, 'has_encoded_data':True})
        html = re.sub(r'<script\b[^>]*>.*?</script>', '', html, flags=re.S)
        script = (Path(__file__).resolve().parents[1] / 'static/js/main.js').read_text(encoding='utf-8')
        with sync_playwright() as playwright:
            try: browser = playwright.chromium.launch(channel='chrome', headless=True)
            except Error as error: raise unittest.SkipTest(str(error))
            try:
                page = browser.new_page()
                page.route('**/*', lambda route: route.abort())
                page.set_content(html)
                page.evaluate('window.Chart={defaults:{font:{}}}')
                page.add_script_tag(content=script)
                page.evaluate('initScenarioPanels()')
                field = page.locator('[data-scenario-change]')
                apply = page.get_by_role('button', name='Apply', exact=True)
                page.locator('[data-scenario-type]').select_option('egg_price_increase')
                for invalid in ('', 'abc', '10abc', '10%%', 'Infinity', '-101'):
                    field.fill(invalid); apply.click()
                    self.assertTrue(page.locator('[data-scenario-error]').inner_text())
                    self.assertIn('332.00', page.locator('[data-result=revenue]').inner_text())
                    self.assertEqual(page.locator('[data-scenario-label]').first.inner_text(), 'Current Profit')
                field.fill('10%'); apply.click()
                self.assertIn('335.20', page.locator('[data-result=revenue]').inner_text())
                self.assertIn('315.20', page.locator('[data-result=profit]').inner_text())
                self.assertIn('20.00', page.locator('[data-result=expenses]').inner_text())
                self.assertFalse(page.locator('[data-scenario-error]').inner_text())
                field.fill('abc'); apply.click()
                self.assertIn('335.20', page.locator('[data-result=revenue]').inner_text())
                field.fill('0'); apply.click()
                self.assertIn('332.00', page.locator('[data-result=revenue]').inner_text())
                page.set_viewport_size({'width':390, 'height':844})
                field.fill(''); apply.click()
                self.assertEqual(field.get_attribute('aria-invalid'), 'true')
            finally: browser.close()
