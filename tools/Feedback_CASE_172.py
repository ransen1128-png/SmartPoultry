"""Feedback browser test CASE-172."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["172", *sys.argv[1:]]))

from tools.automation_browser import expect


from tools.feedback_browser import FeedbackBrowserCase


class FeedbackCase172(FeedbackBrowserCase):
    def test_case_172_feedback(self):
        self.open_feedback()
        expect(self.page.get_by_role('heading', name='My Feedback', exact=True)).to_be_visible()
        expect(self.page.get_by_text('You have not submitted feedback yet.', exact=True)).to_be_visible()
