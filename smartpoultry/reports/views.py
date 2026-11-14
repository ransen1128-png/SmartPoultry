import csv
from datetime import timedelta

from django.http import HttpResponse
from django.db.models import Sum
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from .models import Report
from .serializers import ReportSerializer


class ReportViewSet(viewsets.ModelViewSet):
    """ViewSet for managing reports."""
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Report.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False,methods=['get'],url_path='branch-expenses')
    def branch_expenses(self,request):
        from .branch_analysis import expense_report
        from rest_framework.response import Response
        report,rows=expense_report(request)
        if request.query_params.get('export')!='csv': return Response(report)
        response=HttpResponse(content_type='text/csv')
        response['Content-Disposition']='attachment; filename="branch-expenses.csv"'
        writer=csv.writer(response)
        writer.writerow(['Financial date','Branch','Expense type','Description','Amount','Distribution date'])
        def safe(value):
            text=str(value or '')
            return "'"+text if text.lstrip().startswith(('=','+','-','@')) else text
        for row in rows:
            writer.writerow([row.date,safe(row.branch.name if row.branch else 'Unassigned'),row.expense_type,safe(row.description),row.amount,row.inventory_distribution.date if row.inventory_distribution_id else ''])
        return response

    @action(detail=False,methods=['get'],url_path='feed-usage')
    def feed_usage(self,request):
        from .branch_analysis import feed_report
        from rest_framework.response import Response
        return Response(feed_report(request))

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download a CSV export for this report using only the owner's records."""
        report = self.get_object()
        filename = f"{report.report_type}_report_{report.start_date}_to_{report.end_date}.csv"
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        self._write_report_csv(writer, report)
        return response

    def _write_report_csv(self, writer, report):
        from expenses.models import Expense
        from flocks.models import Flock
        from inventory.models import Inventory
        from production.models import MortalityRecord, ProductionRecord
        from revenue.models import Revenue

        user = report.user
        revenue_records = Revenue.objects.filter(
            user=user,
            date__gte=report.start_date,
            date__lte=report.end_date,
        ).select_related('flock', 'branch','production').order_by('date', 'created_at')
        expense_records = Expense.objects.filter(
            user=user,
            date__gte=report.start_date,
            date__lte=report.end_date,
        ).select_related('branch').order_by('date', 'created_at')
        production_records = ProductionRecord.objects.filter(
            user=user,
            date__gte=report.start_date,
            date__lte=report.end_date,
        ).select_related('flock', 'branch').order_by('date', 'created_at')
        mortality_records = MortalityRecord.objects.filter(
            user=user,
            date__gte=report.start_date,
            date__lte=report.end_date,
        ).select_related('flock', 'branch').order_by('date', 'created_at')
        inventory_items = Inventory.objects.filter(user=user).order_by('item_type', 'name')
        flocks = Flock.objects.filter(user=user).select_related('branch').order_by('branch__name', 'flock_id')

        total_revenue = revenue_records.aggregate(total=Sum('total_amount'))['total'] or 0
        total_expenses = expense_records.aggregate(total=Sum('amount'))['total'] or 0
        total_profit = total_revenue - total_expenses
        total_eggs = production_records.filter(product_type='eggs').aggregate(total=Sum('quantity'))['total'] or 0
        total_mortality = mortality_records.aggregate(total=Sum('quantity'))['total'] or 0
        active_birds = flocks.filter(status='active').aggregate(total=Sum('quantity'))['total'] or 0

        writer.writerow(['SMARTPOULTRY Report Export'])
        writer.writerow(['Report Type', report.get_report_type_display()])
        writer.writerow(['Title', report.title])
        writer.writerow(['User', user.username])
        writer.writerow(['Date Range', f'{report.start_date} to {report.end_date}'])
        writer.writerow(['Generated At', report.generated_at])
        writer.writerow([])

        writer.writerow(['Summary'])
        writer.writerow(['Total Revenue', total_revenue])
        writer.writerow(['Total Expenses', total_expenses])
        writer.writerow(['Profit', total_profit])
        writer.writerow(['Eggs Produced', total_eggs])
        writer.writerow(['Mortality', total_mortality])
        writer.writerow(['Active Chicken', active_birds])
        writer.writerow([])

        writer.writerow(['Monthly Financial Summary'])
        writer.writerow(['Month', 'Revenue', 'Expenses', 'Profit'])
        month_start = report.start_date.replace(day=1)
        while month_start <= report.end_date:
            if month_start.month == 12:
                next_month = month_start.replace(year=month_start.year + 1, month=1)
            else:
                next_month = month_start.replace(month=month_start.month + 1)
            period_start = max(month_start, report.start_date)
            period_end = min(next_month, report.end_date + timedelta(days=1))
            month_revenue = revenue_records.filter(date__gte=period_start, date__lt=period_end).aggregate(total=Sum('total_amount'))['total'] or 0
            month_expenses = expense_records.filter(date__gte=period_start, date__lt=period_end).aggregate(total=Sum('amount'))['total'] or 0
            writer.writerow([
                month_start.strftime('%B %Y'),
                month_revenue,
                month_expenses,
                month_revenue - month_expenses,
            ])
            month_start = next_month
        writer.writerow([])

        writer.writerow(['Revenue Records'])
        writer.writerow(['Date', 'Branch', 'Type', 'Flock', 'Quantity', 'Unit', 'Price Per Unit', 'Total Amount', 'Notes','Buyer Name','Buyer Contact','Buyer Address','Order Number','Transaction Number','Egg Size'])
        def safe_sale_text(value):
            text=str(value or '')
            return "'"+text if text.lstrip().startswith(('=','+','-','@')) else text
        for item in revenue_records:
            writer.writerow([
                item.date,
                item.branch.name if item.branch else '',
                item.get_revenue_type_display(),
                item.flock.flock_id if item.flock else '',
                item.quantity,
                item.unit,
                item.price_per_unit,
                item.total_amount,
                item.notes,
                *[safe_sale_text(value) for value in (item.buyer_name,item.buyer_contact,item.buyer_address,item.order_number,item.transaction_number)],
                item.production.get_egg_size_display() if item.production_id else '',
            ])
        writer.writerow([])

        writer.writerow(['Expense Records'])
        writer.writerow(['Date', 'Branch', 'Type', 'Description', 'Category', 'Amount', 'Notes','Returned Quantity','Return Unit','Returned Item'])
        for item in expense_records:
            writer.writerow([
                item.date,
            item.branch.name if item.branch else '',
                item.get_expense_type_display(),
                item.description,
                item.category,
                item.amount,
                item.notes,
                item.return_quantity,
                safe_sale_text(item.return_unit),
                safe_sale_text(item.return_item_name),
            ])
        writer.writerow([])

        writer.writerow(['Production Records'])
        writer.writerow(['Date', 'Branch', 'Product Type', 'Flock', 'Quantity', 'Unit', 'Notes','Egg Size'])
        for item in production_records:
            writer.writerow([
                item.date,
            item.branch.name if item.branch else '',
                item.get_product_type_display(),
                item.flock.flock_id,
                item.quantity,
                item.unit,
                item.notes,
                item.get_egg_size_display(),
            ])
        writer.writerow([])

        writer.writerow(['Mortality Records'])
        writer.writerow(['Date', 'Branch', 'Flock', 'Quantity', 'Reason', 'Description', 'Notes'])
        for item in mortality_records:
            writer.writerow([
                item.date,
            item.branch.name if item.branch else '',
                item.flock.flock_id,
                item.quantity,
                item.get_reason_display(),
                item.description,
                item.notes,
            ])
        writer.writerow([])

        writer.writerow(['Flocks'])
        writer.writerow(['Branch', 'Flock ID', 'Breed', 'Quantity', 'Status', 'Date Added', 'Expected Production Date', 'Notes'])
        for item in flocks:
            writer.writerow([
            item.branch.name if item.branch else '',
                item.flock_id,
                item.get_breed_display(),
                item.quantity,
                item.get_status_display(),
                item.date_added,
                item.expected_production_date or '',
                item.notes,
            ])
        writer.writerow([])

        writer.writerow(['Inventory'])
        writer.writerow(['Type', 'Name', 'Quantity', 'Unit', 'Cost Per Unit', 'Total Value', 'Date Added', 'Notes','Package Size','Content Unit','Total Content'])
        for item in inventory_items:
            writer.writerow([
                item.get_item_type_display(),
                item.name,
                item.quantity,
                item.unit,
                item.cost_per_unit,
                item.total_value,
                item.date_added,
                item.notes,
                item.package_size if item.package_size is not None else '',
                item.content_unit,
                item.total_content if item.total_content is not None else '',
            ])
