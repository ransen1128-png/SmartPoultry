"""Notifications browser test CASE-160."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["160", *sys.argv[1:]]))

import re

from playwright.sync_api import expect

from production.models import ProductionRecord
from tools.notifications_browser import NotificationsBrowserCase


class NotificationsCase160(NotificationsBrowserCase):
    def test_case_160_notifications(self):
        eggs = ProductionRecord.objects.create(
            user=self.user, branch=self.branch, flock=self.flock, product_type='eggs',
            egg_size='medium', quantity=14, unit='units', date=self.today,
        )
        self.post_api('/api/revenue/order/', {
            'buyer_name': 'QA Egg Buyer', 'date': self.today.isoformat(),
            'items': [{'production': eggs.pk, 'quantity': 4, 'price_per_unit': 8}],
        })
        notification = self.notification('Successfully added eggs revenue')
        expect(notification).to_contain_text(re.compile(r'PHP 32(?:\.0+)? from 4(?:\.0+)? units'))
