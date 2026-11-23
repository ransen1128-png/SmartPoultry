"""Change History browser test CASE-154."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["154", *sys.argv[1:]]))

from playwright.sync_api import expect

from core.models import AuditEvent
from tools.change_history_browser import ChangeHistoryBrowserCase


class ChangeHistoryCase154(ChangeHistoryBrowserCase):
    def test_case_154_change_history(self):
        card = self.event_card(self.mortality_update)
        note = card.get_by_label('Correction note', exact=True)
        expect(note).to_have_value('')
        card.get_by_role('button', name='Add note', exact=True).click()
        self.assertTrue(note.evaluate('field => field.validity.valueMissing'))
        expect(self.page.get_by_text('Please fill out this field.', exact=True)).to_be_visible()
        expect(self.page).to_have_url(f'{self.live_server_url}{self.history_url}')
        self.assertFalse(AuditEvent.objects.filter(owner=self.user, action='note').exists())
