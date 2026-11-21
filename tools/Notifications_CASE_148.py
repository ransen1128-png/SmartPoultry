"""Notifications browser test CASE-148."""

import re

from playwright.sync_api import expect

from tools.notifications_browser import NotificationsBrowserCase


class NotificationsCase148(NotificationsBrowserCase):
    def test_case_148_notifications(self):
        self.post_api('/api/inventory/items/', {
            'item_type': 'feed', 'name': self.item_name, 'quantity': 5, 'unit': 'sacks',
            'package_size': 25, 'content_unit': 'kg', 'cost_per_unit': 1000,
            'date_added': self.today.isoformat(),
        })
        notification = self.notification(f'Successfully added {self.item_name} to feed and inventory')
        expect(notification.locator('span > small')).to_have_text(
            re.compile(r'^5(?:\.0+)? sacks of feed inventory was added\.$'),
        )
