"""Change History browser test CASE-143."""

from playwright.sync_api import expect

from core.models import AuditEvent
from tools.change_history_browser import ChangeHistoryBrowserCase


class ChangeHistoryCase143(ChangeHistoryBrowserCase):
    def test_case_143_change_history(self):
        card = self.event_card(self.mortality_update)
        note = card.get_by_label('Correction note', exact=True)
        expect(note).to_have_value('')
        card.get_by_role('button', name='Add note', exact=True).click()
        self.assertTrue(note.evaluate('field => field.validity.valueMissing'))
        expect(self.page.get_by_text('Please fill out this field.', exact=True)).to_be_visible()
        expect(self.page).to_have_url(f'{self.live_server_url}{self.history_url}')
        self.assertFalse(AuditEvent.objects.filter(owner=self.user, action='note').exists())
