"""Feedback browser test CASE-159."""

from playwright.sync_api import expect

from tools.feedback_browser import FeedbackBrowserCase


class FeedbackCase159(FeedbackBrowserCase):
    def test_case_159_feedback(self):
        self.open_feedback()
        for field in ('Subject', 'Rating', 'Message'):
            expect(self.form.get_by_label(field, exact=True)).to_be_visible()
        rating = self.form.get_by_label('Rating', exact=True)
        expect(rating).to_have_value('5')
        expect(rating.locator('option:checked')).to_have_text('5 - Excellent')
