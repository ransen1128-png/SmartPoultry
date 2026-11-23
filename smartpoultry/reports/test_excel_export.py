from datetime import date
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from openpyxl import load_workbook

from expenses.models import Expense
from reports.models import Report
from revenue.models import Revenue

XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


class ExcelReportExportTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='excel-owner')
        self.other = User.objects.create_user(username='excel-other')
        self.client.force_login(self.user)

    def report(self, kind, start, end):
        return Report.objects.create(user=self.user, report_type=kind, title=f'{kind} report', start_date=start, end_date=end)

    def workbook(self, report):
        response = self.client.get(f'/api/reports/{report.id}/download/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], XLSX)
        self.assertIn('.xlsx"', response['Content-Disposition'])
        return load_workbook(BytesIO(response.content))

    def column_a(self, sheet):
        return [cell.value for cell in sheet['A'] if isinstance(cell.value, str)]

    def test_weekly_report_has_daily_breakdown_and_formatted_record_sheets(self):
        Revenue.objects.create(user=self.user, revenue_type='eggs', quantity=Decimal('10'), unit='tray',
                               price_per_unit=Decimal('100'), date=date(2026, 11, 10), notes='=HYPERLINK("http://x","click")')
        Revenue.objects.create(user=self.other, revenue_type='eggs', quantity=Decimal('1'), unit='tray',
                               price_per_unit=Decimal('900'), date=date(2026, 11, 10), notes='Other sale')
        Expense.objects.create(user=self.user, expense_type='feed', description='Feed', amount=Decimal('300'), date=date(2026, 11, 9))
        wb = self.workbook(self.report('weekly', date(2026, 11, 8), date(2026, 11, 14)))

        self.assertEqual(wb.sheetnames, ['Summary', 'Revenue', 'Expenses', 'Production', 'Mortality', 'Flocks', 'Inventory'])
        summary = self.column_a(wb['Summary'])
        self.assertIn('Daily Breakdown', summary)
        self.assertEqual([label for label in summary if label[:4] in ('Sun,', 'Mon,', 'Tue,', 'Wed,', 'Thu,', 'Fri,', 'Sat,')],
                         ['Sun, Nov 08', 'Mon, Nov 09', 'Tue, Nov 10', 'Wed, Nov 11', 'Thu, Nov 12', 'Fri, Nov 13', 'Sat, Nov 14'])
        self.assertEqual(wb['Summary']['A7'].value, 1000)  # Total revenue card, owner only
        self.assertEqual(wb['Summary']['C7'].value, 700)   # Net profit card

        revenue = wb['Revenue']
        self.assertEqual(revenue['A2'].value.date(), date(2026, 11, 10))
        self.assertEqual(revenue['A2'].number_format, 'mmm d, yyyy')
        self.assertEqual(revenue.max_row, 3)  # header, one owner row, totals row
        self.assertEqual(revenue['H3'].value, '=SUBTOTAL(109,H2:H2)')
        notes = revenue['O2']
        self.assertEqual(notes.data_type, 's')  # user text is never a live formula
        self.assertEqual(revenue.freeze_panes, 'A2')
        self.assertIn('Revenue', revenue.tables)
        self.assertEqual(revenue['H3'].data_type, 'f')  # our own totals stay live formulas
        self.assertIsNone(revenue['G3'].value)  # unit prices are not totalled

    def test_breakdowns_add_up_records_sharing_a_day_and_branch(self):
        from core.models import Branch, Farm
        farm = Farm.objects.create(owner=self.user, name='Farm', location='Town', established_date=date(2026, 1, 1),
                                   contact_email='farm@example.com', contact_phone='09123456789')
        branch = Branch.objects.create(farm=farm, name='Labogon Branch')
        for price in ('7', '12', '180'):
            Revenue.objects.create(user=self.user, branch=branch, revenue_type='eggs', quantity=Decimal('10'),
                                   unit='tray', price_per_unit=Decimal(price), date=date(2026, 11, 14))
        sheet = self.workbook(self.report('weekly', date(2026, 11, 8), date(2026, 11, 14)))['Summary']
        rows = {sheet.cell(row=row, column=1).value: row for row in range(1, sheet.max_row + 1)}
        self.assertEqual(sheet.cell(row=rows['Sat, Nov 14'], column=2).value, 1990)
        self.assertEqual(sheet.cell(row=rows['Labogon Branch'], column=2).value, 1990)
        profit = sheet.cell(row=rows['Sat, Nov 14'], column=4)
        self.assertEqual((profit.data_type, profit.value), ('f', f"=B{rows['Sat, Nov 14']}-C{rows['Sat, Nov 14']}"))

    def test_breakdown_granularity_follows_report_type(self):
        cases = [
            ('daily', date(2026, 11, 14), date(2026, 11, 14), None, 0),
            ('monthly', date(2026, 11, 1), date(2026, 11, 30), 'Weekly Breakdown', 6),
            ('annual', date(2026, 1, 1), date(2026, 12, 31), 'Monthly Breakdown', 12),
        ]
        for kind, start, end, heading, periods in cases:
            with self.subTest(kind=kind):
                summary = self.column_a(self.workbook(self.report(kind, start, end))['Summary'])
                self.assertIn('By Branch', summary)
                for other in ('Daily Breakdown', 'Weekly Breakdown', 'Monthly Breakdown'):
                    (self.assertIn if other == heading else self.assertNotIn)(other, summary)
                if heading:
                    start_row = summary.index(heading)
                    rows = summary[start_row + 2:summary.index('Total', start_row)]
                    self.assertEqual(len(rows), periods)

    def test_empty_period_sheets_explain_there_are_no_records(self):
        wb = self.workbook(self.report('weekly', date(2026, 1, 5), date(2026, 1, 11)))
        self.assertEqual(wb['Mortality']['A2'].value, 'No records in this period.')

    def test_other_users_cannot_download_the_report(self):
        report = self.report('weekly', date(2026, 11, 8), date(2026, 11, 14))
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f'/api/reports/{report.id}/download/').status_code, 404)
