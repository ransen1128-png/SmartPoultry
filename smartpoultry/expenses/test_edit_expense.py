from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import AuditEvent, Branch, Farm
from expenses.models import Expense


class EditExpenseTests(TestCase):
    """DEF-11: an owner can correct an expense, and the correction is kept in Change History."""

    def account(self, name):
        user = get_user_model().objects.create_user(name, email=f'{name}@example.com', password='Secret!123')
        farm = Farm.objects.create(owner=user, name=f'{name} Farm', location='Argao', established_date='2026-01-01',
                                   contact_email=user.email, contact_phone='09170000000')
        return user, Branch.objects.create(farm=farm, name=f'{name} Branch')

    def setUp(self):
        self.user, self.branch = self.account('alpha')
        self.other, self.other_branch = self.account('beta')
        self.expense = Expense.objects.create(user=self.user, branch=self.branch, expense_type='feed', description='Feed',
                                              amount='30.00', date='2026-11-20')
        self.client.force_login(self.user)

    def patch(self, pk=None, **data):
        return self.client.patch(f'/api/expenses/{pk or self.expense.pk}/', data, content_type='application/json')

    def test_correction_is_saved_with_its_reason(self):
        self.assertEqual(self.patch(amount='45.50', correction_reason='Wrong receipt amount').status_code, 200)
        self.expense.refresh_from_db()
        self.assertEqual(str(self.expense.amount), '45.50')
        event = AuditEvent.objects.get(object_type='expenses.Expense', object_id=self.expense.pk, action='updated')
        self.assertEqual((event.before['amount'], event.after['amount'], event.reason), ('30.00', '45.50', 'Wrong receipt amount'))

    def test_other_accounts_cannot_edit_or_receive_the_expense(self):
        self.assertEqual(self.patch(branch=self.other_branch.pk).status_code, 400)
        self.client.force_login(self.other)
        self.assertEqual(self.patch(amount='1.00').status_code, 404)

    def test_page_has_the_edit_mode(self):
        page = self.client.get(reverse('expenses'))
        for text in ('expenseCorrectionReason', 'Edit Expense', 'Update Expense'):
            self.assertContains(page, text)

    def test_negative_amounts_are_rejected(self):
        data = {'branch': self.branch.pk, 'expense_type': 'feed', 'description': 'x', 'amount': '-5', 'date': '2026-11-20'}
        created = self.client.post('/api/expenses/', data, content_type='application/json')
        self.assertEqual((created.status_code, self.patch(amount='-5').status_code), (400, 400))
        self.assertContains(created, 'cannot be negative', status_code=400)
        self.expense.refresh_from_db()
        self.assertEqual((str(self.expense.amount), Expense.objects.count()), ('30.00', 1))
