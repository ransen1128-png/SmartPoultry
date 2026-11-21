"""Change History browser test CASE-146."""

from tools.change_history_browser import ChangeHistoryBrowserCase


class ChangeHistoryCase146(ChangeHistoryBrowserCase):
    def test_case_146_change_history(self):
        self.assert_correction(self.production_update, '12.00', '14.00', self.production_reason)
