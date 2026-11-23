"""Admin Operations Selenium test CASE-178."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['178', *sys.argv[1:]]))

from tools.automation_browser import expect
from tools.admin_operations_browser import AdminOperationsBrowserCase


class AdminOperationsCase178(AdminOperationsBrowserCase):
    def test_case_178_resolved_feedback_empty(self):
        self.filter_feedback('resolved')
        expect(self.page.get_by_text('No feedback found.', exact=True)).to_be_visible()
        expect(self.page.get_by_role('link', name='Read Comment', exact=True)).to_have_count(0)
