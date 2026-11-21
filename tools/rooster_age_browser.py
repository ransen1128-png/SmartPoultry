"""Browser fixtures for Rooster Age Estimator saved-result and validation cases."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.files import File
from PIL import Image
from playwright.sync_api import expect

from core.models import RoosterAgeEstimate
from tools.feed_inventory_browser import FeedInventoryBrowserCase


class RoosterAgeBrowserCase(FeedInventoryBrowserCase):
    age_display = 'Experimental estimate: 8.5 months'

    def setUp(self):
        super().setUp()
        self.estimator_url = f'{self.live_server_url}/rooster-age-estimator/'
        media_root = self.enterContext(TemporaryDirectory())
        self.enterContext(self.settings(MEDIA_ROOT=media_root))

    def open_estimator(self):
        self.page.goto(self.estimator_url)
        expect(self.page.get_by_role('heading', name='Rooster Age Estimator', exact=True)).to_be_visible()

    def submit_without_photo(self, mode):
        self.open_estimator()
        photo = self.page.locator('#photos')
        expect(photo).to_have_value('')
        submissions = []

        def track_submission(request):
            if request.url == self.estimator_url and request.method == 'POST':
                submissions.append(request)

        self.page.on('request', track_submission)
        self.page.locator(f'button[name="analysis_mode"][value="{mode}"]').click()
        self.assertTrue(photo.evaluate('input => input.validity.valueMissing'))
        message = photo.evaluate('input => input.validationMessage')
        self.assertRegex(message, r'(?i)select.*file')
        expect(self.page.get_by_text(message, exact=True)).to_be_visible()
        expect(self.page).to_have_url(self.estimator_url)
        self.assertFalse(submissions, 'The form submitted without a photo')
        self.assertFalse(RoosterAgeEstimate.objects.filter(user=self.user).exists())
        return message

    def saved_estimate(self, *, measured=False, age_display=None):
        photo = Path(os.environ.get('SMARTPOULTRY_TEST_CHICKEN_IMAGE', r'C:\Users\Administrator\Downloads\chicken.jpg'))
        self.assertTrue(photo.is_file(), f'Chicken photo not found: {photo}')
        with Image.open(photo) as image:
            width, height = image.size
        box = {'xyxy': [145, 194, 177, 225], 'score': 0.8}
        anatomy = {
            'status': 'completed', 'image_width': width, 'image_height': height,
            'legs': [], 'spurs': [box], 'masks': [], 'measurements': [],
        }
        if measured:
            anatomy['masks'].append({**box, 'polygon': [[145, 194], [177, 205], [162, 225]]})
            anatomy['measurements'].append({
                'length_px': 20.0, 'physical_length_cm': None, 'truncated_at_frame': False,
                'centerline': [[150, 205], [170, 205]],
            })

        with photo.open('rb') as image_file:
            return RoosterAgeEstimate.objects.create(
                user=self.user, photo=File(image_file, name=photo.name), photo_name=photo.name,
                estimated_age_range=age_display or self.age_display,
                spur_observations='Synthetic saved analysis for browser testing.',
                analysis={
                    'analysis_mode': 'full', 'age_prediction_status': 'experimental',
                    'anatomy': anatomy,
                },
            )

    def open_saved_estimate(self, estimate):
        self.open_estimator()
        self.page.get_by_role('link', name='View saved analysis', exact=True).and_(
            self.page.locator(f'a[href="?estimate={estimate.pk}#latest-results"]'),
        ).click()
        expect(self.page).to_have_url(f'{self.estimator_url}?estimate={estimate.pk}#latest-results')
        results = self.page.locator('#latest-results')
        expect(results.get_by_role('heading', name='Saved Analysis', exact=True)).to_be_visible()
        card = results.locator('.rooster-result-card')
        expect(card).to_have_count(1)
        expect(card.get_by_text(estimate.photo_name, exact=True)).to_be_visible()
        image = card.get_by_role('img', name='Uploaded image 1', exact=True)
        expect(image).to_be_visible()
        self.page.wait_for_function('img => img.complete && img.naturalWidth > 0', arg=image.element_handle())
        return card
