"""Feedback browser test CASE-158."""

from tools.feedback_browser import FeedbackBrowserCase


class FeedbackCase158(FeedbackBrowserCase):
    def test_case_158_feedback(self):
        self.open_feedback()
        self.form.get_by_label('Subject', exact=True).fill('QA feedback subject')
        self.assert_required_field_blocks_submission('Message')
