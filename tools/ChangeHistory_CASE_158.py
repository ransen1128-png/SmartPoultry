"""Change History browser test CASE-158."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["158", *sys.argv[1:]]))

from playwright.sync_api import expect

from core.models import AuditEvent
from tools.change_history_browser import ChangeHistoryBrowserCase


class ChangeHistoryCase158(ChangeHistoryBrowserCase):
    def test_case_158_change_history(self):
        card = self.assert_correction(self.mortality_update, '2', '3', self.mortality_reason)
        note = 'QA: Recount was confirmed against the branch log.'
        card.get_by_label('Correction note', exact=True).fill(note)
        card.get_by_role('button', name='Add note', exact=True).click()

        event = AuditEvent.objects.get(owner=self.user, action='note', reason=note)
        self.assertEqual(event.after['audit_event_id'], self.mortality_update.pk)
        note_card = self.event_card(event)
        expect(note_card.get_by_text(f'Reason: {note}', exact=True)).to_be_visible()
        self.assert_correction(self.mortality_update, '2', '3', self.mortality_reason)
