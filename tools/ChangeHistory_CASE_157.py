"""Change History browser test CASE-157."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["157", *sys.argv[1:]]))

from tools.change_history_browser import ChangeHistoryBrowserCase


class ChangeHistoryCase157(ChangeHistoryBrowserCase):
    def test_case_157_change_history(self):
        self.assert_correction(self.production_update, '12.00', '14.00', self.production_reason)
