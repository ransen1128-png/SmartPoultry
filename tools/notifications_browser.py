"""Shared fixtures for Notifications browser cases."""

from tools.automation_browser import expect


from tools.feed_inventory_browser import FeedInventoryBrowserCase


class NotificationsBrowserCase(FeedInventoryBrowserCase):
    branch_name = 'QA Sample Branch'

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def post_api(self, path, payload):
        response = self.client.post(path, payload, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)

    def notification(self, title):
        self.page.goto(f'{self.live_server_url}/notifications/')
        expect(self.page.get_by_role('heading', name='Notifications', exact=True)).to_be_visible()
        item = self.page.locator('.notification-list li').filter(has_text=title)
        expect(item).to_have_count(1)
        expect(item).to_be_visible()
        return item
