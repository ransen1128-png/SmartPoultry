import csv

from django.http import HttpResponse
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
        """Download this report as a formatted Excel workbook with only the owner's records."""
        from .excel_export import build_report_workbook
        report = self.get_object()
        response = HttpResponse(
            build_report_workbook(report),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        filename = f"{report.report_type}_report_{report.start_date}_to_{report.end_date}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
