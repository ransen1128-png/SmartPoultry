"""Rooster Age Estimator browser test CASE-124."""

from playwright.sync_api import expect

from tools.rooster_age_browser import RoosterAgeBrowserCase


class RoosterAgeEstimatorCase124(RoosterAgeBrowserCase):
    def test_case_124_unscaled_measurement_uses_pixels(self):
        card = self.open_saved_estimate(self.saved_estimate(measured=True))
        expect(card.locator('.rooster-age-estimate')).to_have_text(self.age_display)
        expect(card.get_by_text('Spur outline detected', exact=False)).to_be_visible()
        length = card.get_by_text('20.0 pixels of visible spur centerline', exact=False)
        expect(length).to_be_visible()
        expect(length).to_contain_text('Add a known image scale to convert pixels to centimeters.')
        expect(length).not_to_contain_text('cm using your supplied scale')
