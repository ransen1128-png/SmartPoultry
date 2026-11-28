"""Formatted Excel workbook for a saved report.

Layout:
  Summary     title block with links to every sheet; key figures with the change
              versus the previous period and the profit margin; a breakdown
              sized to the report type (weekly: by day, monthly: by week,
              quarterly/annual: by month) with a revenue-vs-expenses chart; a
              by-branch breakdown (charted for daily reports); revenue and
              expenses by type with shares and an expense-mix pie chart.
  Revenue, Expenses, Production, Mortality
              records in the report period as filterable Excel tables with a
              SUBTOTAL row that follows the active filter.
  Flocks, Inventory
              current snapshot at export time.
"""
import calendar
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.db.models import Sum
from django.db.models.functions import Length
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.hyperlink import Hyperlink
from openpyxl.worksheet.table import Table, TableStyleInfo

BRAND = '1F6F43'
BRAND_LIGHT = 'E8F3EC'
MUTED = '6B7280'
PESO = '"₱"#,##0.00;[Red]-"₱"#,##0.00'
QTY = '#,##0.00'
COUNT = '#,##0'
DATE = 'mmm d, yyyy'
THIN = Side(style='thin', color='D1D5DB')
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HEADER_FILL = PatternFill('solid', fgColor=BRAND)
HEADER_FONT = Font(bold=True, color='FFFFFF')
TOTAL_FILL = PatternFill('solid', fgColor=BRAND_LIGHT)
PERCENT = '0.0%'
GOOD = '1E7B34'
BAD = 'C62828'
DATA_SHEETS = ('Revenue', 'Expenses', 'Production', 'Mortality', 'Flocks', 'Inventory')
FORMATS = {'money': PESO, 'rate': PESO, 'qty': QTY, 'count': COUNT, 'date': DATE}


def report_records(report):
    """Owner-scoped records for the report period."""
    from expenses.models import Expense
    from flocks.models import Flock
    from inventory.models import Inventory
    from production.models import MortalityRecord, ProductionRecord
    from revenue.models import Revenue

    period = {'user': report.user, 'date__gte': report.start_date, 'date__lte': report.end_date}
    return {
        'revenue': Revenue.objects.filter(**period).select_related('flock', 'branch', 'production').order_by('date', 'created_at'),
        'expenses': Expense.objects.filter(**period).select_related('branch').order_by('date', 'created_at'),
        'production': ProductionRecord.objects.filter(**period).select_related('flock', 'branch').order_by('date', 'created_at'),
        'mortality': MortalityRecord.objects.filter(**period).select_related('flock', 'branch').order_by('date', 'created_at'),
        'inventory': Inventory.objects.filter(user=report.user).order_by('item_type', 'name'),
        'flocks': Flock.objects.filter(user=report.user).select_related('branch').order_by('branch__name', Length('flock_id'), 'flock_id'),  # 02 before 100
    }


def _put(ws, row, column, value, number_format=None, formula=False):
    cell = ws.cell(row=row, column=column, value=value)
    # openpyxl turns any string starting with '=' into a formula; user-entered
    # text (notes, buyer names) must never execute in the recipient's Excel.
    # Only formulas this module builds itself pass formula=True.
    if not formula and isinstance(value, str) and value.startswith('='):
        cell.data_type = 's'
    if number_format:
        cell.number_format = number_format
    return cell


def _period_unit(report):
    span = (report.end_date - report.start_date).days + 1
    kind = report.report_type
    if kind == 'daily' or span == 1:
        return None
    if kind == 'weekly' or (kind not in ('monthly', 'quarterly', 'annual') and span <= 14):
        return 'day'
    if kind == 'monthly' or (kind not in ('quarterly', 'annual') and span <= 62):
        return 'week'
    return 'month'


def _periods(report, unit):
    """Yield (label, first_day, last_day) covering the report range exactly."""
    start, end = report.start_date, report.end_date
    if unit == 'day':
        day = start
        while day <= end:
            yield day.strftime('%a, %b %d'), day, day
            day += timedelta(days=1)
    elif unit == 'week':
        first, number = start, 1
        while first <= end:
            last = min(first + timedelta(days=6 - first.weekday()), end)  # weeks end on Sunday
            yield f"Week {number} ({first:%b %d} – {last:%b %d})", first, last
            first, number = last + timedelta(days=1), number + 1
    else:
        first = start
        while first <= end:
            following = first.replace(year=first.year + 1, month=1, day=1) if first.month == 12 else first.replace(month=first.month + 1, day=1)
            last = min(following - timedelta(days=1), end)
            yield first.strftime('%B %Y'), first, last
            first = following


def _daily_totals(queryset, field, **filters):
    # order_by() clears the record ordering; otherwise Django adds the ordering
    # columns (created_at) to GROUP BY and returns one row per record.
    rows = queryset.filter(**filters).order_by().values('date').annotate(total=Sum(field))
    return {row['date']: row['total'] or 0 for row in rows}


def _branch_totals(queryset, field, **filters):
    rows = queryset.filter(**filters).order_by().values('branch__name').annotate(total=Sum(field))
    return {row['branch__name'] or 'Unassigned': row['total'] or 0 for row in rows}


def _breakdown(ws, row, title, labels, series):
    """Write a Period | Revenue | Expenses | Profit | Eggs | Mortality table with live formulas.

    Returns (next_row, header_row, first_data_row, last_data_row); last < first when empty.
    """
    ws.cell(row=row, column=1, value=title).font = Font(bold=True, size=12, color=BRAND)
    row += 1
    header_row = row
    headers = ['Branch' if title == 'By Branch' else 'Period', 'Revenue', 'Expenses', 'Profit', 'Eggs Produced', 'Mortality']
    _header(ws, row, headers)
    first = row + 1
    for label, (revenue, expenses, eggs, deaths) in zip(labels, series):
        row += 1
        _put(ws, row, 1, label)
        _put(ws, row, 2, revenue, PESO)
        _put(ws, row, 3, expenses, PESO)
        _put(ws, row, 4, f'=B{row}-C{row}', PESO, formula=True)
        _put(ws, row, 5, eggs, COUNT)
        _put(ws, row, 6, deaths, COUNT)
        for column in range(1, 7):
            ws.cell(row=row, column=column).border = BOX
    last = row
    if last >= first:
        row += 1
        _total_row(ws, row, 6)
        for column, (letter, fmt) in enumerate(zip('BCDEF', (PESO, PESO, PESO, COUNT, COUNT)), 2):
            _put(ws, row, column, f'=SUM({letter}{first}:{letter}{last})', fmt, formula=True)
    else:
        row += 1
        _put(ws, row, 1, 'No records in this period.').font = Font(italic=True, color=MUTED)
    return row + 2, header_row, first, last


def _header(ws, row, headers):
    for column, header in enumerate(headers, 1):
        cell = ws.cell(row=row, column=column, value=header)
        cell.fill, cell.font, cell.border = HEADER_FILL, HEADER_FONT, BOX
        cell.alignment = Alignment(horizontal='center' if column > 1 else 'left')


def _total_row(ws, row, width):
    _put(ws, row, 1, 'Total')
    for column in range(1, width + 1):
        cell = ws.cell(row=row, column=column)
        cell.font, cell.fill, cell.border = Font(bold=True), TOTAL_FILL, BOX


def _share_table(ws, row, title, label_header, items):
    """Label | Amount | Share table; Share is a live formula. Returns (next_row, header_row, first, last)."""
    ws.cell(row=row, column=1, value=title).font = Font(bold=True, size=12, color=BRAND)
    row += 1
    header_row = row
    _header(ws, row, [label_header, 'Amount', 'Share'])
    first, last = row + 1, row + len(items)
    total_row = last + 1
    for label, amount in items:
        row += 1
        _put(ws, row, 1, label)
        _put(ws, row, 2, amount, PESO)
        _put(ws, row, 3, f'=IF($B${total_row}=0,0,B{row}/$B${total_row})', PERCENT, formula=True)
        for column in range(1, 4):
            ws.cell(row=row, column=column).border = BOX
    if items:
        row += 1
        _total_row(ws, row, 3)
        _put(ws, row, 2, f'=SUM(B{first}:B{last})', PESO, formula=True)
        _put(ws, row, 3, f'=IF(B{row}=0,0,1)', PERCENT, formula=True)
    else:
        row += 1
        _put(ws, row, 1, 'No records in this period.').font = Font(italic=True, color=MUTED)
    return row + 2, header_row, first, last


def _type_totals(queryset, type_field, amount_field, model):
    names = dict(model._meta.get_field(type_field).flatchoices)
    rows = queryset.order_by().values(type_field).annotate(total=Sum(amount_field)).order_by('-total')
    return [(names.get(row[type_field], row[type_field] or 'Other'), row['total'] or 0) for row in rows]


def _shift_months(day, months):
    index = day.year * 12 + day.month - 1 - months
    year, month = divmod(index, 12)
    month += 1
    return day.replace(year=year, month=month, day=min(day.day, calendar.monthrange(year, month)[1]))


def _previous_period(report):
    """The comparable range just before the report.

    Monthly/quarterly/annual reports starting on the 1st compare with the same
    calendar dates one month/quarter/year earlier (so month-to-date compares
    with the same days last month); other reports with the same number of days.
    """
    start, end = report.start_date, report.end_date
    months = {'monthly': 1, 'quarterly': 3, 'annual': 12}.get(report.report_type)
    if months and start.day == 1:
        previous_end = _shift_months(end, months)
        if end.day == calendar.monthrange(end.year, end.month)[1]:
            previous_end = previous_end.replace(day=calendar.monthrange(previous_end.year, previous_end.month)[1])
        return _shift_months(start, months), previous_end
    span = (end - start).days + 1
    return start - timedelta(days=span), end - timedelta(days=span)


def _period_totals(user, start, end):
    from expenses.models import Expense
    from production.models import MortalityRecord, ProductionRecord
    from revenue.models import Revenue
    period = {'user': user, 'date__gte': start, 'date__lte': end}
    revenue = Revenue.objects.filter(**period).aggregate(t=Sum('total_amount'))['t'] or 0
    expenses = Expense.objects.filter(**period).aggregate(t=Sum('amount'))['t'] or 0
    return {
        'revenue': revenue, 'expenses': expenses, 'profit': revenue - expenses,
        'eggs': ProductionRecord.objects.filter(product_type='eggs', **period).aggregate(t=Sum('quantity'))['t'] or 0,
        'mortality': MortalityRecord.objects.filter(**period).aggregate(t=Sum('quantity'))['t'] or 0,
    }


def _change(current, previous, higher_is_better):
    """Return (text, colour) describing the change from the previous period."""
    if not previous:
        return ('No prior data' if not current else 'New this period'), MUTED
    percent = (Decimal(current) - Decimal(previous)) / abs(Decimal(previous)) * 100
    if percent == 0:
        return '■ No change', MUTED
    good = (percent > 0) == higher_is_better
    arrow = '▲' if percent > 0 else '▼'
    return f'{arrow} {abs(percent):.1f}% vs prior', (GOOD if good else BAD)


def _bar_chart(ws, anchor, header_row, first, last, title):
    chart = BarChart()
    chart.type, chart.grouping, chart.title = 'col', 'clustered', title
    chart.add_data(Reference(ws, min_col=2, max_col=3, min_row=header_row, max_row=last), titles_from_data=True)
    chart.set_categories(Reference(ws, min_col=1, min_row=first, max_row=last))
    chart.series[0].graphicalProperties.solidFill = '2E7D32'
    chart.series[1].graphicalProperties.solidFill = 'C62828'
    chart.y_axis.numFmt = '"₱"#,##0'
    # openpyxl 3.1 hides axes unless told otherwise.
    chart.x_axis.delete = False
    chart.y_axis.delete = False
    chart.legend.position = 't'
    _no_overlay(chart)
    chart.width, chart.height = 23, 7.5
    ws.add_chart(chart, anchor)


def _no_overlay(chart):
    # Excel otherwise draws the title and legend on top of the plot area and axis labels.
    chart.legend.overlay = False
    if chart.title is not None:
        chart.title.overlay = False


def _pie_chart(ws, anchor, header_row, first, last, title):
    chart = PieChart()
    chart.title = title
    chart.add_data(Reference(ws, min_col=2, min_row=header_row, max_row=last), titles_from_data=True)
    chart.set_categories(Reference(ws, min_col=1, min_row=first, max_row=last))
    # Percent only; Excel otherwise also prints series name, category and value.
    chart.dataLabels = DataLabelList(showPercent=True, showVal=False, showCatName=False,
                                     showSerName=False, showLegendKey=False)
    chart.legend.position = 'r'
    _no_overlay(chart)
    chart.width, chart.height = 11, 6.5
    ws.add_chart(chart, anchor)


CHART_ROWS = 16  # rows covered by a 7.5 cm chart at the default row height


def _summary_sheet(wb, report, records):
    from expenses.models import Expense
    from revenue.models import Revenue
    ws = wb.active
    ws.title = 'Summary'
    ws.sheet_properties.tabColor = BRAND
    revenue, expenses, production, mortality = (records[key] for key in ('revenue', 'expenses', 'production', 'mortality'))
    current = _period_totals(report.user, report.start_date, report.end_date)
    previous_start, previous_end = _previous_period(report)
    previous = _period_totals(report.user, previous_start, previous_end)
    margin = (Decimal(current['profit']) / Decimal(current['revenue']) * 100) if current['revenue'] else None
    figures = [
        ('Total Revenue', 'revenue', PESO, True),
        ('Total Expenses', 'expenses', PESO, False),
        (f'Net Profit · {margin:.1f}% margin' if margin is not None else 'Net Profit', 'profit', PESO, True),
        ('Eggs Produced', 'eggs', COUNT, True),
        ('Mortality', 'mortality', COUNT, False),
    ]

    ws.merge_cells('A1:F1')
    title = ws['A1']
    title.value = f'SMARTPOULTRY · {report.get_report_type_display()}'
    title.font = Font(bold=True, size=18, color='FFFFFF')
    title.fill = HEADER_FILL
    title.alignment = Alignment(vertical='center', indent=1)
    ws.row_dimensions[1].height = 34
    ws.merge_cells('A2:F2')
    ws['A2'] = f'{report.title}  ·  {_range_text(report.start_date, report.end_date)}'
    ws['A2'].font = Font(bold=True, size=12)
    ws.merge_cells('A3:F3')
    generated = timezone.localtime(report.generated_at)
    ws['A3'] = f'Prepared for {report.user.username}  ·  Generated {generated:%b %d, %Y %I:%M %p} {generated.tzname()}'
    ws['A3'].font = Font(italic=True, color=MUTED)
    for column, name in enumerate(DATA_SHEETS, 1):
        cell = ws.cell(row=4, column=column, value=f'→ {name}')
        cell.hyperlink = Hyperlink(ref=cell.coordinate, location=f"'{name}'!A1", display=name)
        cell.font = Font(color='1565C0', underline='single', size=9)
        cell.alignment = Alignment(horizontal='center')

    ws['A6'] = 'Key Figures'
    ws['A6'].font = Font(bold=True, size=12, color=BRAND)
    cards = [(label, current[key], fmt, _change(current[key], previous[key], better)) for label, key, fmt, better in figures]
    active = records['flocks'].filter(status='active').aggregate(t=Sum('quantity'))['t'] or 0
    cards.append(('Active Chicken (now)', active, COUNT, ('Current count', MUTED)))
    for column, (label, value, fmt, (change, colour)) in enumerate(cards, 1):
        head = ws.cell(row=7, column=column, value=label)
        head.font, head.fill, head.border = Font(bold=True, color=MUTED, size=9), TOTAL_FILL, BOX
        head.alignment = Alignment(horizontal='center')
        cell = _put(ws, 8, column, value, fmt)
        cell.font, cell.border = Font(bold=True, size=14), BOX
        cell.alignment = Alignment(horizontal='center')
        note = ws.cell(row=9, column=column, value=change)
        note.font, note.border = Font(size=9, bold=True, color=colour), BOX
        note.alignment = Alignment(horizontal='center')
    ws.row_dimensions[8].height = 26
    _put(ws, 10, 1, f'Compared with {_range_text(previous_start, previous_end)}.').font = Font(italic=True, color=MUTED, size=9)

    row = 12
    charted = False
    unit = _period_unit(report)
    if unit:
        daily = (_daily_totals(revenue, 'total_amount'), _daily_totals(expenses, 'amount'),
                 _daily_totals(production, 'quantity', product_type='eggs'), _daily_totals(mortality, 'quantity'))
        labels, series = [], []
        for label, first, last in _periods(report, unit):
            days = [first + timedelta(days=offset) for offset in range((last - first).days + 1)]
            labels.append(label)
            series.append(tuple(sum((source.get(day, 0) for day in days), Decimal(0)) for source in daily))
        title = {'day': 'Daily Breakdown', 'week': 'Weekly Breakdown', 'month': 'Monthly Breakdown'}[unit]
        row, header_row, first, last = _breakdown(ws, row, title, labels, series)
        _bar_chart(ws, f'A{row}', header_row, first, last, f'Revenue vs Expenses ({title.split()[0]})')
        row += CHART_ROWS
        charted = True

    by_branch = [_branch_totals(revenue, 'total_amount'), _branch_totals(expenses, 'amount'),
                 _branch_totals(production, 'quantity', product_type='eggs'), _branch_totals(mortality, 'quantity')]
    branches = sorted(set().union(*by_branch), key=lambda name: (name == 'Unassigned', name.lower()))
    row, header_row, first, last = _breakdown(ws, row, 'By Branch', branches,
                                              [tuple(source.get(name, 0) for source in by_branch) for name in branches])
    if not charted and last >= first:
        _bar_chart(ws, f'A{row}', header_row, first, last, 'Revenue vs Expenses by Branch')
        row += CHART_ROWS

    row, *_ = _share_table(ws, row, 'Revenue by Type', 'Type', _type_totals(revenue, 'revenue_type', 'total_amount', Revenue))
    table_top = row
    row, header_row, first, last = _share_table(ws, row, 'Expenses by Type', 'Type',
                                                _type_totals(expenses, 'expense_type', 'amount', Expense))
    if last >= first:
        _pie_chart(ws, f'D{table_top}', header_row, first, last, 'Expense Mix')
        row = max(row, table_top + 14)

    _put(ws, row, 1, 'Flocks and Inventory sheets show current status at export time; all other figures cover the report period.').font = Font(italic=True, color=MUTED, size=9)
    ws.column_dimensions['A'].width = 34
    for letter in 'BCDEF':
        ws.column_dimensions[letter].width = 20
    ws.sheet_view.showGridLines = False
    _print_setup(ws, report)


def _range_text(start, end):
    return f'{start:%B %d, %Y}' if start == end else f'{start:%B %d, %Y} – {end:%B %d, %Y}'


def _data_sheet(wb, report, title, columns, rows, color, empty='No records in this period.'):
    """columns: [(header, kind)] where kind is text/date/money/rate/qty/count.

    money/qty/count get a SUBTOTAL total that follows the active filter; rate
    (unit prices) is formatted as money but never totalled.
    """
    ws = wb.create_sheet(title)
    ws.sheet_properties.tabColor = color
    for column, (header, _) in enumerate(columns, 1):
        cell = ws.cell(row=1, column=column, value=header)
        cell.font = Font(bold=True)
    widths = [len(header) + 4 for header, _ in columns]
    for row_number, values in enumerate(rows, 2):
        for column, ((_, kind), value) in enumerate(zip(columns, values), 1):
            if value is None:
                value = ''
            _put(ws, row_number, column, value, FORMATS.get(kind))
            widths[column - 1] = max(widths[column - 1], 14 if kind == 'date' else len(str(value)) + 2)
    last_column = get_column_letter(len(columns))
    if rows:
        last_row = len(rows) + 1
        table = Table(displayName=title.replace(' ', ''), ref=f'A1:{last_column}{last_row}')
        table.tableStyleInfo = TableStyleInfo(name='TableStyleMedium7', showRowStripes=True)
        ws.add_table(table)
        total_row = last_row + 1
        _put(ws, total_row, 1, 'Total (visible rows)').font = Font(bold=True)
        for column, (_, kind) in enumerate(columns, 1):
            if kind in ('money', 'qty', 'count') and column > 1:
                letter = get_column_letter(column)
                cell = _put(ws, total_row, column, f'=SUBTOTAL(109,{letter}2:{letter}{last_row})', FORMATS[kind], formula=True)
                cell.font = Font(bold=True)
        for column in range(1, len(columns) + 1):
            ws.cell(row=total_row, column=column).fill = TOTAL_FILL
            ws.cell(row=total_row, column=column).border = Border(top=Side(style='double', color=BRAND))
    else:
        for column in range(1, len(columns) + 1):
            ws.cell(row=1, column=column).fill = HEADER_FILL
            ws.cell(row=1, column=column).font = HEADER_FONT
        _put(ws, 2, 1, empty).font = Font(italic=True, color=MUTED)
    for column, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(column)].width = min(max(width, 10), 48)
    ws.freeze_panes = 'A2'
    _print_setup(ws, report, title_rows='1:1')


def _print_setup(ws, report, title_rows=None):
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_options.horizontalCentered = True
    if title_rows:
        ws.print_title_rows = title_rows
    ws.oddHeader.center.text = f'SMARTPOULTRY · {report.get_report_type_display()} · &A'
    ws.oddFooter.left.text = f'{report.start_date} to {report.end_date}'
    ws.oddFooter.right.text = 'Page &P of &N'


def build_report_workbook(report):
    records = report_records(report)
    wb = Workbook()
    wb.properties.title = report.title
    wb.properties.creator = 'SMARTPOULTRY'
    _summary_sheet(wb, report, records)

    _data_sheet(wb, report, 'Revenue', [
        ('Date', 'date'), ('Branch', 'text'), ('Type', 'text'), ('Flock', 'text'), ('Quantity', 'qty'), ('Unit', 'text'),
        ('Price Per Unit', 'rate'), ('Total Amount', 'money'), ('Egg Size', 'text'), ('Buyer Name', 'text'),
        ('Buyer Contact', 'text'), ('Buyer Address', 'text'), ('Order Number', 'text'), ('Transaction Number', 'text'), ('Notes', 'text'),
    ], [(r.date, r.branch.name if r.branch else '', r.get_revenue_type_display(), r.flock.flock_id if r.flock else '',
         r.quantity, r.unit, r.price_per_unit, r.total_amount, r.production.get_egg_size_display() if r.production_id else '',
         r.buyer_name, r.buyer_contact, r.buyer_address, r.order_number, r.transaction_number, r.notes)
        for r in records['revenue']], '2E7D32')

    _data_sheet(wb, report, 'Expenses', [
        ('Date', 'date'), ('Branch', 'text'), ('Type', 'text'), ('Description', 'text'), ('Category', 'text'),
        ('Amount', 'money'), ('Returned Quantity', 'qty'), ('Return Unit', 'text'), ('Returned Item', 'text'), ('Notes', 'text'),
    ], [(e.date, e.branch.name if e.branch else '', e.get_expense_type_display(), e.description, e.category, e.amount,
         e.return_quantity, e.return_unit, e.return_item_name, e.notes) for e in records['expenses']], 'C62828')

    _data_sheet(wb, report, 'Production', [
        ('Date', 'date'), ('Branch', 'text'), ('Product Type', 'text'), ('Flock', 'text'), ('Quantity', 'qty'),
        ('Unit', 'text'), ('Egg Size', 'text'), ('Notes', 'text'),
    ], [(p.date, p.branch.name if p.branch else '', p.get_product_type_display(), p.flock.flock_id, p.quantity, p.unit,
         p.get_egg_size_display(), p.notes) for p in records['production']], 'F9A825')

    _data_sheet(wb, report, 'Mortality', [
        ('Date', 'date'), ('Branch', 'text'), ('Flock', 'text'), ('Quantity', 'count'), ('Reason', 'text'),
        ('Description', 'text'), ('Notes', 'text'), ('Breed', 'text'),
    ], [(m.date, m.branch.name if m.branch else '', m.flock.flock_id, m.quantity, m.get_reason_display(), m.description, m.notes,
         m.flock.get_breed_display())
        for m in records['mortality']], '6D4C41')

    _data_sheet(wb, report, 'Flocks', [
        ('Branch', 'text'), ('Flock ID', 'text'), ('Breed', 'text'), ('Quantity', 'count'), ('Status', 'text'),
        ('Date Added', 'date'), ('Expected Production Date', 'date'), ('Notes', 'text'),
    ], [(f.branch.name if f.branch else '', f.flock_id, f.get_breed_display(), f.quantity, f.get_status_display(),
         f.date_added, f.expected_production_date, f.notes) for f in records['flocks']], '1565C0',
        empty='No flocks recorded.')

    _data_sheet(wb, report, 'Inventory', [
        ('Type', 'text'), ('Name', 'text'), ('Quantity', 'qty'), ('Unit', 'text'), ('Cost Per Unit', 'rate'),
        ('Total Value', 'money'), ('Date Added', 'date'), ('Package Size', 'qty'), ('Content Unit', 'text'),
        ('Total Content', 'qty'), ('Notes', 'text'),
    ], [(i.get_item_type_display(), i.name, i.quantity, i.unit, i.cost_per_unit, i.total_value, i.date_added,
         i.package_size, i.content_unit, i.total_content, i.notes) for i in records['inventory']], '6A1B9A',
        empty='No inventory items recorded.')

    stream = BytesIO()
    wb.save(stream)
    return stream.getvalue()
