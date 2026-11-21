"""Shared fixtures for the Scenario Analysis browser cases."""

from playwright.sync_api import expect

from tools.ml_predictions_browser import NovemberFinancialBrowserCase


class ScenarioAnalysisBrowserCase(NovemberFinancialBrowserCase):
    def setUp(self):
        super().setUp()
        self.page.get_by_role('link', name='Scenario Analysis').click()
        expect(self.page).to_have_url(f'{self.live_server_url}/scenario-analysis/')
        self.panel = self.page.locator('.scenario-panel')

    def apply_change(self, change, scenario='feed_price_increase'):
        self.panel.locator('[data-scenario-type]').select_option(scenario)
        self.panel.get_by_label('Scenario change').fill(change)
        self.panel.get_by_role('button', name='Apply', exact=True).click()

    def assert_results(self, *, revenue, expenses, profit):
        for name, value in (('revenue', revenue), ('expenses', expenses), ('profit', profit)):
            expect(self.panel.locator(f'[data-result="{name}"]')).to_have_text(value)
