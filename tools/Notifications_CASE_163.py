"""Notifications browser test CASE-163."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["163", *sys.argv[1:]]))

from tools.automation_browser import expect

from datetime import timedelta


from flocks.models import Flock
from tools.notifications_browser import NotificationsBrowserCase


class NotificationsCase163(NotificationsBrowserCase):
    def test_case_163_notifications(self):
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
