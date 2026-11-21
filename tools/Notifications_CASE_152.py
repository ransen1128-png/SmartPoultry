"""Notifications browser test CASE-152."""

from datetime import timedelta

from playwright.sync_api import expect

from flocks.models import Flock
from tools.notifications_browser import NotificationsBrowserCase


class NotificationsCase152(NotificationsBrowserCase):
    def test_case_152_notifications(self):
        placement = self.today - timedelta(days=30)
        Flock.objects.create(
            user=self.user, branch=self.branch, flock_id='02', breed='broilers',
            quantity=25, placement_date=placement,
        )
        notification = self.notification('Broilers ready: 02')
        expect(notification).to_contain_text(f'{self.branch.name}: flock 02')
        expect(notification).to_contain_text(
            f'Production and sale are allowed from {placement + timedelta(days=25)}',
        )
        expect(notification).to_contain_text(f'expected window ends {placement + timedelta(days=60)}')
