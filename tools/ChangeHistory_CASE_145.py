"""Change History browser test CASE-145."""

from tools.change_history_browser import ChangeHistoryBrowserCase


class ChangeHistoryCase145(ChangeHistoryBrowserCase):
    def test_case_145_change_history(self):
        self.assert_correction(self.mortality_update, '2', '3', self.mortality_reason)
