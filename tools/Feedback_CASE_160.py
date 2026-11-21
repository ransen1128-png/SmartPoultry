"""Feedback browser test CASE-160."""

from playwright.sync_api import expect

from tools.feedback_browser import FeedbackBrowserCase


class FeedbackCase160(FeedbackBrowserCase):
    def test_case_160_feedback(self):
        self.open_feedback()
        rating = self.form.get_by_label('Rating', exact=True)
        rating.select_option(label='4 - Good')
        expect(rating).to_have_value('4')
        expect(rating.locator('option:checked')).to_have_text('4 - Good')
