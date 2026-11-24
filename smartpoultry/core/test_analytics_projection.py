from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from expenses.models import Expense
from revenue.models import Revenue


class AnalyticsProjectionTests(TestCase):
    """AT-33: an unfinished month must not be projected as a collapse in revenue."""

    def setUp(self):
        self.user = get_user_model().objects.create_user('projection-owner')
        self.client.force_login(self.user)

    def month(self, month, revenue, expense):
        day = date(2026, month, 2)
        Revenue.objects.create(user=self.user, revenue_type='eggs', quantity=1, price_per_unit=revenue, date=day)
        Expense.objects.create(user=self.user, expense_type='feed', description='Feed', amount=expense, date=day)

    def chart(self):
        with mock.patch('core.views.timezone.localdate', return_value=date(2026, 11, 25)):
            response = self.client.get(reverse('analytics'))
        data = response.context['chart_data']
        return response, [value for value in data['actualVsPredicted']['predictedRevenue'] if value is not None], data['profit']['values']

    def test_unfinished_month_does_not_change_the_projection(self):
        for month, revenue in ((6, 6840), (7, 7200), (8, 7488), (9, 7920), (10, 8280)):
            self.month(month, revenue, 5000)
        _, before, profit_before = self.chart()
        self.month(11, 380, 35)
        _, after, profit_after = self.chart()
        self.assertEqual((before, profit_before), (after, profit_after))
        # Average of the last three completed months (7896) plus the recent slope (360).
        self.assertEqual(after[0], 8256.0)

    def test_current_month_is_used_when_it_is_the_only_one(self):
        self.month(11, 1000, 400)
        _, revenue, _ = self.chart()
        self.assertEqual(revenue, [1000.0] * 6)

    def test_page_names_its_method(self):
        response, _, _ = self.chart()
        self.assertContains(response, 'Recent-trend projection')
        self.assertNotContains(response, 'SQLite')
