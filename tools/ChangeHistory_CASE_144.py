"""Change History browser test CASE-144."""

from playwright.sync_api import expect

from tools.change_history_browser import ChangeHistoryBrowserCase


class ChangeHistoryCase144(ChangeHistoryBrowserCase):
    def test_case_144_change_history(self):
        articles = self.page.locator('main article')
        expect(self.event_card(self.production_update)).to_be_visible()
        self.page.locator('select[name="type"]').select_option('production.MortalityRecord')
        self.page.get_by_role('button', name='Filter', exact=True).click()
        expect(self.page).to_have_url(f'{self.live_server_url}{self.history_url}?type=production.MortalityRecord')
        expect(self.event_card(self.mortality_update)).to_be_visible()
        expect(self.event_card(self.production_update)).to_have_count(0)
        headings = articles.get_by_role('heading').all_text_contents()
        self.assertTrue(headings)
        self.assertTrue(all('production.MortalityRecord #' in heading for heading in headings), headings)
