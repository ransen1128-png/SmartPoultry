from django import forms
from production.models import MortalityRecord, ProductionRecord


class StyledModelForm(forms.ModelForm):
    """Apply Bootstrap styling to generated form fields."""
    date_input_fields = {'date'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css_class = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'
            field.widget.attrs['class'] = css_class
            if name in self.date_input_fields:
                field.widget = forms.DateInput(
                    attrs={'class': 'form-control', 'type': 'date'},
                    format='%Y-%m-%d',
                )


class BranchFlockSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        flock = getattr(value, 'instance', None)
        if flock:
            option['attrs']['data-branch-id'] = str(flock.branch_id or '')
            option['attrs']['data-product-type'] = {'layers': 'eggs', 'broilers': 'meat_ready'}.get(flock.breed, 'both')
            option['attrs']['data-ready-from'] = flock.ready_from.isoformat() if flock.ready_from else ''
            option['attrs']['data-ready-until'] = flock.readiness_window_end.isoformat() if flock.readiness_window_end else ''
        return option


class ProductionRecordForm(StyledModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product_type'].choices = [
            ('eggs', 'Eggs'),
            ('meat_ready', 'Meat Ready'),
        ]
        if user is not None:
            self.fields['flock'].queryset = self.fields['flock'].queryset.filter(user=user, status='active').exclude(branch__status='inactive')
            self.fields['branch'].queryset = self.fields['branch'].queryset.filter(farm__owner=user, status='active')
            if not self.instance.pk:self.fields['flock'].queryset=self.fields['flock'].queryset.filter(quantity__gt=0)
        branch_id = self.data.get('branch') if self.is_bound else getattr(self.instance, 'branch_id', None)
        if branch_id:
            breeds = set(self.fields['flock'].queryset.filter(branch_id=branch_id).values_list('breed', flat=True)) if str(branch_id).isdigit() else set()
            if breeds and 'other' not in breeds:
                allowed = {'layers': 'eggs', 'broilers': 'meat_ready'}
                self.fields['product_type'].choices = [(key, label) for key, label in self.fields['product_type'].choices if key in {allowed.get(breed) for breed in breeds}]

    def clean(self):
        cleaned_data = super().clean()
        flock = cleaned_data.get('flock')
        product_type = cleaned_data.get('product_type')
        if product_type=='eggs' and not cleaned_data.get('egg_size') and (not self.instance.pk or self.instance.egg_size):
            self.add_error('egg_size','Choose Small, Medium or Large for these eggs.')
        expected_product = {
            'layers': 'eggs',
            'broilers': 'meat_ready',
        }.get(flock.breed if flock else None)
        if expected_product and product_type != expected_product:
            self.add_error('product_type', 'The product type must match the selected flock breed.')
        branch = cleaned_data.get('branch')
        if flock and flock.branch_id != (branch.pk if branch else None):
            self.add_error('flock', 'Select a flock from the selected branch.')
        return cleaned_data

    class Meta:
        model = ProductionRecord
        fields = ['branch', 'flock', 'product_type', 'egg_size', 'quantity', 'date']
        widgets = {
            'flock': BranchFlockSelect(),
        }


class MortalityRecordForm(StyledModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['flock'].queryset = self.fields['flock'].queryset.filter(user=user, status='active').exclude(branch__status='inactive')
            self.fields['branch'].queryset = self.fields['branch'].queryset.filter(farm__owner=user, status='active')
            if not self.instance.pk:self.fields['flock'].queryset=self.fields['flock'].queryset.filter(quantity__gt=0)
        self.fields['branch'].required = True

    def clean(self):
        cleaned_data = super().clean()
        branch = cleaned_data.get('branch')
        flock = cleaned_data.get('flock')
        if flock and branch and flock.branch_id != branch.pk:
            self.add_error('flock', 'Select a flock from the selected branch.')
        return cleaned_data

    class Meta:
        model = MortalityRecord
        fields = ['branch', 'flock', 'quantity', 'reason', 'date', 'description', 'notes']
        labels = {
            'flock': 'Flock ID to reduce',
        }
        help_texts = {
            'flock': 'Choose the flock whose quantity will be reduced by this mortality record.',
            'quantity': 'This number will be subtracted from the selected flock.',
        }
        widgets = {
            'flock': BranchFlockSelect(),
            'description': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
