"""Shared correction fixtures for Change History browser cases."""

from playwright.sync_api import expect

from core.models import AuditEvent
from production.models import MortalityRecord, ProductionRecord
from tools.feed_inventory_browser import FeedInventoryBrowserCase


class ChangeHistoryBrowserCase(FeedInventoryBrowserCase):
    mortality_reason = 'Corrected mortality count after recounting the flock.'
    production_reason = 'Corrected production count after recounting the eggs.'
    history_url = '/change-history/'

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        fields = {'branch': self.branch.pk, 'flock': self.flock.pk, 'date': self.today.isoformat()}
        mortality = MortalityRecord.objects.create(
            user=self.user, branch=self.branch, flock=self.flock, quantity=2, reason='accident', date=self.today,
        )
        response = self.client.post(f'/mortality-records/{mortality.pk}/edit/', {
            **fields, 'quantity': 3, 'reason': 'accident', 'correction_reason': self.mortality_reason,
        })
        self.assertRedirects(response, '/mortality-records/', fetch_redirect_response=False)
        eggs = ProductionRecord.objects.create(
            user=self.user, branch=self.branch, flock=self.flock,
            product_type='eggs', egg_size='medium', quantity=12, date=self.today,
        )
        response = self.client.post(f'/production-records/{eggs.pk}/edit/', {
            **fields, 'product_type': 'eggs', 'egg_size': 'medium', 'quantity': 14,
            'correction_reason': self.production_reason,
        })
        self.assertRedirects(response, '/production-records/', fetch_redirect_response=False)
        updates = AuditEvent.objects.filter(owner=self.user, action='updated')
        self.mortality_update = updates.get(object_type='production.MortalityRecord', object_id=mortality.pk)
        self.production_update = updates.get(object_type='production.ProductionRecord', object_id=eggs.pk)
        self.page.get_by_role('link', name='Change History').click()
        expect(self.page).to_have_url(f'{self.live_server_url}{self.history_url}')
        expect(self.page.get_by_role('heading', name='Change History', exact=True)).to_be_visible()

    def event_card(self, event):
        return self.page.locator('main article').filter(
            has=self.page.get_by_role('heading').filter(
                has_text=f'{event.action} \u00b7 {event.object_type} #{event.object_id}',
            ),
        )

    def assert_correction(self, event, before, after, reason):
        card = self.event_card(event)
        expect(card).to_have_count(1)
        expect(card.get_by_text(f'Reason: {reason}', exact=True)).to_be_visible()
        quantity = card.get_by_role('row').filter(
            has=self.page.get_by_role('cell', name='quantity', exact=True),
        )
        expect(quantity.get_by_role('cell')).to_have_text(['quantity', before, after])
        return card
