"""Shared navigation for Settings browser cases."""

from tools.automation_browser import expect


from tools.feed_inventory_browser import FeedInventoryBrowserCase


class SettingsBrowserCase(FeedInventoryBrowserCase):
    def open_settings(self):
        self.page.locator('nav a[href^="/settings/"]').filter(has_text='Settings').click()
        expect(self.page.get_by_role('heading', name='Settings', exact=True)).to_be_visible()

    def open_security(self):
        self.open_settings()
        self.page.get_by_role('tab', name='Account Security', exact=True).click()
        panel = self.page.locator('#security-panel')
        expect(panel).to_be_visible()
        return panel

    def open_preferences(self):
        self.open_settings()
        self.page.get_by_role('tab', name='Notification Preferences', exact=True).click()
        panel = self.page.locator('#notifications-panel')
        expect(panel).to_be_visible()
        return panel
