"""Feedback browser test CASE-161."""

from playwright.sync_api import expect

from tools.feedback_browser import FeedbackBrowserCase


class FeedbackCase161(FeedbackBrowserCase):
    def test_case_161_feedback(self):
        self.open_feedback()
        expect(self.page.get_by_role('heading', name='My Feedback', exact=True)).to_be_visible()
        expect(self.page.get_by_text('You have not submitted feedback yet.', exact=True)).to_be_visible()
