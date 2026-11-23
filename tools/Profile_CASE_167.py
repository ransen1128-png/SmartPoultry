"""Profile browser test CASE-167."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["167", *sys.argv[1:]]))

from tools.automation_browser import expect


from tools.profile_browser import ProfileBrowserCase


class ProfileCase167(ProfileBrowserCase):
    def test_case_167_profile(self):
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
