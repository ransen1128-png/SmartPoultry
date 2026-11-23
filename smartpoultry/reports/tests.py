import csv
import io
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from openpyxl import load_workbook
from rest_framework.test import APIClient

from expenses.models import Expense
from .models import Report


class ReportWorkflowTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username='report-workflow-owner')
        self.other = get_user_model().objects.create_user(username='report-workflow-other')
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.end = date(2026, 11, 22)
        Expense.objects.create(user=self.owner, expense_type='feed', description='Owner feed', amount=625, date=self.end)
        Expense.objects.create(user=self.other, expense_type='feed', description='Private other feed', amount=9999, date=self.end)
        Expense.objects.create(user=self.owner, expense_type='feed', description='Outside range', amount=500, date=date(2025, 12, 1))

    def test_all_generation_periods_download_correct_owner_totals(self):
        starts = {'daily': self.end, 'weekly': self.end - timedelta(days=6),
                  'monthly': self.end.replace(day=1), 'annual': self.end.replace(month=1, day=1)}
        for period, start in starts.items():
            with self.subTest(period=period):
                created = self.client.post('/api/reports/', {'report_type': period, 'title': period + ' report',
                    'start_date': str(start), 'end_date': str(self.end)}, format='json')
                self.assertEqual(created.status_code, 201)
                report = Report.objects.get(pk=created.data['id'])
                self.assertEqual(report.user, self.owner)
                downloaded = self.client.get(f'/api/reports/{report.pk}/download/')
                self.assertEqual(downloaded.status_code, 200)
                self.assertIn('attachment;', downloaded['Content-Disposition'])
                workbook = load_workbook(io.BytesIO(downloaded.content))
                text = ' '.join(str(cell.value) for sheet in workbook for row in sheet.iter_rows() for cell in row if cell.value is not None)
                self.assertEqual(workbook['Summary']['B8'].value, 625)  # Total expenses card
                self.assertIn(f'{start:%B %d, %Y}', workbook['Summary']['A2'].value)
                self.assertIn('Owner feed', text)
                self.assertNotIn('Private other feed', text)
                self.assertNotIn('Outside range', text)
                self.client.force_authenticate(self.other)
                self.assertEqual(self.client.get(f'/api/reports/{report.pk}/download/').status_code, 404)
                self.client.force_authenticate(self.owner)

    def test_filtered_expense_csv_and_invalid_date_recovery(self):
        url = '/api/reports/branch-expenses/'
        self.assertEqual(self.client.get(url, {'start': '2026-11-22', 'end': '2026-11-01'}).status_code, 400)
        params = {'start': '2026-11-01', 'end': '2026-11-22'}
        result = self.client.get(url, params)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data['total'], '625')
        downloaded = self.client.get(url, {**params, 'export': 'csv'})
        self.assertEqual(downloaded.status_code, 200)
        rows = list(csv.reader(io.StringIO(downloaded.content.decode())))
        self.assertEqual(rows[0], ['Financial date', 'Branch', 'Expense type', 'Description', 'Amount', 'Distribution date'])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][3:5], ['Owner feed', '625.00'])
