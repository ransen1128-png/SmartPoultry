"""Shared browser fixtures for Feed & Inventory cases."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.utils import timezone

try:
    from tools.automation_browser import expect, expect_field_error, launch_browser
except ModuleNotFoundError:
    from automation_browser import expect, expect_field_error, launch_browser

from core.models import Branch, Farm
from flocks.models import Flock
from inventory.models import Inventory, InventoryDistribution


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class FeedInventoryBrowserCase(StaticLiveServerTestCase):
    item_name = 'QA Layer Feed'
    branch_name = 'Sample Branch'
    seed_farm = True
    seed_branch = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.browser = launch_browser()
        cls.addClassCleanup(cls.browser.close)

    def setUp(self):
        self.today = timezone.localdate()
        email, password = 'inventory-qa@example.invalid', 'Fixture!123'
        self.user = get_user_model().objects.create_user('inventory-qa', email, password)
        if self.seed_farm:
            self.farm = Farm.objects.create(owner=self.user, name='QA Farm', established_date=self.today)
            if self.seed_branch:
                self.branch = Branch.objects.create(farm=self.farm, name=self.branch_name)
                self.flock = Flock.objects.create(
                    user=self.user, branch=self.branch, flock_id='01', breed='layers', quantity=30,
                )
        self.page = self.browser.new_page(locale='en-US')
        self.addCleanup(self.page.close)
        self.page.goto(f'{self.live_server_url}/login/')
        self.page.get_by_label('Email', exact=True).fill(email)
        self.page.get_by_label('Password', exact=True).fill(password)
        self.page.get_by_role('button', name='Login', exact=True).click()
        expect(self.page).to_have_url(f'{self.live_server_url}/dashboard/')

    def open_inventory(self):
        self.page.goto(f'{self.live_server_url}/inventory/')
        expect(self.page.get_by_role('heading', name='Inventory Management')).to_be_visible()

    def stock_fixture(self):
        return Inventory.objects.create(
            user=self.user, item_type='feed', name=self.item_name, quantity=5,
            unit='sacks', package_size=25, content_unit='kg', cost_per_unit=1000, date_added=self.today,
        )

    def distribution_fixture(self):
        item = self.stock_fixture()
        return InventoryDistribution.objects.create(
            user=self.user, inventory=item, branch=self.branch, quantity=Decimal('2'), date=self.today,
        )

    def inventory_row(self):
        return self.page.locator('#inventoryBody tr').filter(
            has=self.page.get_by_role('cell', name=self.item_name, exact=True),
        )

    def branch_row(self, distribution):
        return self.page.locator('#branchStockBody tr').filter(
            has_text=f'{self.item_name} / #{distribution.pk} /',
        )

    def open_add_item(self):
        self.open_inventory()
        self.page.get_by_role('button', name='Add Item').click()
        expect(self.page.locator('#addInventoryModal')).to_be_visible()

    def fill_item(self, quantity='5'):
        self.open_add_item()
        form = self.page.locator('#addInventoryForm')
        form.locator('[name="name"]').fill(self.item_name)
        form.locator('[name="quantity"]').fill(quantity)
        form.locator('[name="unit"]').select_option('sacks')
        form.locator('[name="package_size"]').fill('25')
        form.locator('[name="content_unit"]').select_option('kg')
        form.locator('[name="cost_per_unit"]').fill('1000')

    def open_distribution(self):
        self.inventory_row().get_by_role('button', name='Distribute', exact=True).click()
        expect(self.page.locator('#distributionModal')).to_be_visible()

    def fill_distribution(self, quantity='2', *, select_branch=True):
        self.open_distribution()
        if select_branch:
            self.page.locator('#distributionBranch').select_option(str(self.branch.pk))
        self.page.locator('#distributionQuantity').fill(quantity)

    def open_branch_usage(self, distribution, quantity):
        self.open_inventory()
        self.branch_row(distribution).get_by_role('button', name='Record use').click()
        expect(self.page.locator('#branchUsageModal')).to_be_visible()
        self.page.locator('#branchUsageQuantity').fill(quantity)
        self.page.locator('#branchUsageReason').fill('Recorded feed usage for the QA flock.')

    def assert_native_error(self, selector, flag):
        field = self.page.locator(selector)
        self.assertTrue(field.evaluate('(field, flag) => field.validity[flag]', flag))
        expect_field_error(field)

    def assert_stock(self, item, quantity):
        item.refresh_from_db()
        self.assertEqual(item.quantity, quantity)
        expect(self.inventory_row().get_by_role('cell').nth(3)).to_contain_text(f'{quantity} sacks')
