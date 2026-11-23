"""Admin Operations Selenium test CASE-182."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['182', *sys.argv[1:]]))

from tools.automation_browser import expect
from tools.admin_operations_browser import AdminOperationsBrowserCase


class AdminOperationsCase182(AdminOperationsBrowserCase):
    def test_case_182_read_new_feedback(self):
        self.filter_feedback('new')
        expect(self.page.get_by_text(self.reviewed_feedback.subject, exact=True)).to_have_count(0)
        self.page.get_by_role('link', name='Read Comment', exact=True).click()
        expect(self.page).to_have_url(f'{self.live_server_url}/admin-dashboard/feedback/{self.feedback.pk}/')
        expect(self.page.get_by_role('heading', name=self.feedback.subject, exact=True)).to_be_visible()
        expect(self.page.get_by_text(f'Rating {self.feedback.rating}/5')).to_be_visible()
