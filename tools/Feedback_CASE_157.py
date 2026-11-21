"""Feedback browser test CASE-157."""

from tools.feedback_browser import FeedbackBrowserCase


class FeedbackCase157(FeedbackBrowserCase):
    def test_case_157_feedback(self):
        self.open_feedback()
        self.form.get_by_label('Message', exact=True).fill('QA feedback message.')
        self.assert_required_field_blocks_submission('Subject')
