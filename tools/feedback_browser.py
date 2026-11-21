"""Shared setup for Feedback browser cases."""

from playwright.sync_api import expect

from core.models import Feedback
from tools.feed_inventory_browser import FeedInventoryBrowserCase


class FeedbackBrowserCase(FeedInventoryBrowserCase):
    def open_feedback(self):
        self.page.locator('nav a[href="/feedback/"]').click()
        expect(self.page).to_have_url(f'{self.live_server_url}/feedback/')
        expect(self.page.get_by_role('heading', name='Feedback', exact=True)).to_be_visible()
        self.form = self.page.locator('main form').filter(
            has=self.page.get_by_role('button', name='Submit Feedback'),
        )

    def assert_required_field_blocks_submission(self, label):
        field = self.form.get_by_label(label, exact=True)
        expect(field).to_have_value('')
        submissions = []

        def track_submission(request):
            if request.method == 'POST' and request.url == f'{self.live_server_url}/feedback/':
                submissions.append(request)

        self.page.on('request', track_submission)
        self.form.get_by_role('button', name='Submit Feedback').click()
        self.assertTrue(field.evaluate('field => field.validity.valueMissing'))
        expect(self.form.get_by_text('Please fill out this field.', exact=True)).to_be_visible()
        self.assertFalse(submissions, 'The incomplete form was submitted')
        self.assertFalse(Feedback.objects.filter(user=self.user).exists())
