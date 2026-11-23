"""Change History browser test CASE-156."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["156", *sys.argv[1:]]))

from tools.change_history_browser import ChangeHistoryBrowserCase


class ChangeHistoryCase156(ChangeHistoryBrowserCase):
    def test_case_156_change_history(self):
        self.assert_correction(self.mortality_update, '2', '3', self.mortality_reason)
