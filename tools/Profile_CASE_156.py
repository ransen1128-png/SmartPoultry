"""Profile browser test CASE-156."""

from playwright.sync_api import expect

from tools.profile_browser import ProfileBrowserCase


class ProfileCase156(ProfileBrowserCase):
    def test_case_156_profile(self):
        self.open_profile()
        first = self.profile_form.get_by_label('First Name', exact=True)
        last = self.profile_form.get_by_label('Last Name', exact=True)
        first.fill('Jamie')
        last.fill('Flores')
        self.save_profile()
        expect(self.page.get_by_text('Profile updated successfully.', exact=True).filter(visible=True)).to_be_visible()
        self.page.reload(wait_until='domcontentloaded')
        expect(first).to_have_value('Jamie')
        expect(last).to_have_value('Flores')
        self.user.refresh_from_db()
        self.assertEqual((self.user.first_name, self.user.last_name), ('Jamie', 'Flores'))
