"""SmartPoultry integration INT-021 (CASE-205)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['205', *sys.argv[1:]]))

from tools.notifications_browser import NotificationsBrowserCase
import Notifications_CASE_160 as workflow_1


class IntegrationCase205(NotificationsBrowserCase):
    def test_int_021(self):
        workflow_1.NotificationsCase160.test_case_160_notifications(self)
