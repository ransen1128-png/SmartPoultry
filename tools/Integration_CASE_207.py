"""SmartPoultry integration INT-023 (CASE-207)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['207', *sys.argv[1:]]))

from tools.notifications_browser import NotificationsBrowserCase
import Notifications_CASE_159 as workflow_1


class IntegrationCase207(NotificationsBrowserCase):
    def test_int_023(self):
        workflow_1.NotificationsCase159.test_case_159_notifications(self)
