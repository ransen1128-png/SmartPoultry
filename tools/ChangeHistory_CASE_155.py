"""Change History browser test CASE-155."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["155", *sys.argv[1:]]))

from tools.automation_browser import expect


from tools.change_history_browser import ChangeHistoryBrowserCase


class ChangeHistoryCase155(ChangeHistoryBrowserCase):
    def test_case_155_change_history(self):
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
