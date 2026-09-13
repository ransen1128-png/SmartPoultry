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


class ProductionRecordForm(StyledModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product_type'].choices = [
            ('eggs', 'Eggs'),
            ('meat_ready', 'Meat Ready'),
        ]
        if user is not None:
            self.fields['flock'].queryset = self.fields['flock'].queryset.filter(user=user)
            self.fields['branch'].queryset = self.fields['branch'].queryset.filter(farm__owner=user)

    def clean(self):
        cleaned_data = super().clean()
        flock = cleaned_data.get('flock')
        product_type = cleaned_data.get('product_type')
        expected_product = {
            'layers': 'eggs',
            'broilers': 'meat_ready',
        }.get(flock.breed if flock else None)
        if expected_product and product_type != expected_product:
            self.add_error('product_type', 'The product type must match the selected flock breed.')
        return cleaned_data

    class Meta:
        model = ProductionRecord
        fields = ['branch', 'flock', 'product_type', 'quantity', 'unit', 'date', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class MortalityRecordForm(StyledModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['flock'].queryset = self.fields['flock'].queryset.filter(user=user)
            self.fields['branch'].queryset = self.fields['branch'].queryset.filter(farm__owner=user)

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
            'description': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
