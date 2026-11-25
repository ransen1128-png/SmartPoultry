"""Health Records pages: vaccinations, medications, diseases and treatments per flock."""
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from flocks.models import Flock
from notifications.utils import create_activity_notification
from production.models import HealthRecord
from .forms import StyledModelForm
from .input_rules import RecordDateFormMixin


class HealthRecordForm(RecordDateFormMixin, StyledModelForm):
    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        flocks = Flock.objects.filter(user=user)
        available = flocks.filter(status='active').exclude(branch__status='inactive').values('pk')
        # Keep the record's own flock selectable when correcting an old record.
        field = self.fields['flock']
        field.queryset = flocks.filter(pk__in=available) | flocks.filter(pk=self.instance.flock_id)
        field.queryset = field.queryset.select_related('branch')
        field.label_from_instance = lambda flock: flock.display_label
        if not self.instance.pk:
            self.fields['date'].initial = timezone.localdate

    def clean(self):
        data = super().clean()
        details = ('disease_name', 'treatment', 'medication', 'vaccination_name', 'notes')
        if data.get('health_status') in ('sick', 'treated', 'recovered') and not any(data.get(name) for name in details):
            raise forms.ValidationError('Enter the disease, treatment, medication, vaccination or notes for this record.')
        return data

    class Meta:
        model = HealthRecord
        fields = ['flock', 'date', 'health_status', 'vaccination_name', 'disease_name', 'medication', 'treatment', 'notes']
        labels = {'vaccination_name': 'Vaccination', 'disease_name': 'Disease'}
        widgets = {'treatment': forms.Textarea(attrs={'rows': 3}), 'notes': forms.Textarea(attrs={'rows': 3})}


def owned(request):
    return HealthRecord.objects.filter(flock__user=request.user)


@login_required(login_url='login')
def health_records(request):
    rows = owned(request).exclude(flock__status='inactive').exclude(flock__branch__status='inactive')
    rows = rows.select_related('flock__branch').order_by('-date', '-pk')
    return render(request, 'health_records.html', {'page': Paginator(rows, 50).get_page(request.GET.get('page'))})


def edit(request, record, title, submit_label):
    form = HealthRecordForm(request.POST or None, instance=record, user=request.user)
    if request.method == 'POST' and form.is_valid():
        created = not form.instance.pk
        saved = form.save()
        if created:
            create_activity_notification(
                request.user, 'Successfully added health record',
                f'Recorded {saved.get_health_status_display().lower()} status for flock {saved.flock.display_label} on {saved.date}.',
                saved)
        messages.success(request, 'Health record added.' if created else 'Health record updated.')
        return redirect('health_records')
    return render(request, 'health_record_form.html', {'form': form, 'title': title, 'submit_label': submit_label})


@login_required(login_url='login')
def health_record_create(request):
    return edit(request, None, 'Add Health Record', 'Save Record')


@login_required(login_url='login')
def health_record_update(request, record_id):
    return edit(request, get_object_or_404(owned(request), pk=record_id), 'Edit Health Record', 'Update Record')


@login_required(login_url='login')
def health_record_delete(request, record_id):
    record = get_object_or_404(owned(request), pk=record_id)
    if request.method == 'POST':
        record.delete()
        messages.success(request, 'Health record deleted.')
    return redirect('health_records')
