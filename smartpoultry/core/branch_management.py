"""Owner-scoped branch management; the parent Farm is the original main location."""
from django import forms
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string

from .contact_validation import PHONE_ERROR, valid_contact_phone
from .models import Branch, Farm


class BranchForm(forms.Form):
    branch_name = forms.CharField(label='Branch Name', max_length=255)
    address = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}))
    contact_number = forms.CharField(label='Contact Number', max_length=20,
        widget=forms.TextInput(attrs={'type': 'tel', 'inputmode': 'numeric',
            'minlength': 11, 'pattern': '[0-9]{11,20}', 'title': PHONE_ERROR}))
    description = forms.CharField(label='Description (Optional)', required=False,
        widget=forms.Textarea(attrs={'rows': 2}))
    status = forms.ChoiceField(choices=Branch.STATUS_CHOICES, initial='active')

    def __init__(self, *args, farm, branch=None, **kwargs):
        self.farm, self.branch = farm, branch
        initial = {'status': 'active'}
        if branch:
            initial = {name: getattr(branch, 'name' if name == 'branch_name' else name)
                for name in self.base_fields}
        super().__init__(*args, initial=initial, **kwargs)
        # Existing incomplete legacy records remain editable without erasing data.
        if branch:
            for name in ('address', 'contact_number'):
                self.fields[name].required = False
            self.fields.pop('description')
        for name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'
            field.widget.attrs['id'] = f'branch_{branch.pk if branch else "new"}_{name}'

    def clean_branch_name(self):
        name = self.cleaned_data['branch_name']
        existing = Branch.objects.filter(farm=self.farm, name__iexact=name)
        if self.branch:
            existing = existing.exclude(pk=self.branch.pk)
        if existing.exists():
            raise forms.ValidationError('A branch with this name already exists in your farm.')
        return name

    def clean_contact_number(self):
        value = self.cleaned_data['contact_number']
        if value and not valid_contact_phone(value):
            raise forms.ValidationError(PHONE_ERROR)
        return value


def branch_context(request, farm, *, bound_form=None, edited_branch=None, query=None):
    query = (request.GET.get('q', '') if query is None else query).strip()[:200]
    all_branches = farm.branches.all() if farm else Branch.objects.none()
    has_branches = all_branches.exists()
    branches = list(all_branches.filter(Q(name__icontains=query) | Q(address__icontains=query)).order_by('created_at', 'pk'))
    for branch in branches:
        branch.edit_form = bound_form if edited_branch and branch.pk == edited_branch.pk else BranchForm(farm=farm, branch=branch)
    return {'farm': farm, 'branches': branches, 'has_branches': has_branches,
        'show_farm': bool(farm and (not query or query.casefold() in farm.name.casefold() or query.casefold() in farm.address.casefold())),
        'query': query, 'branch_form': bound_form if bound_form and not edited_branch else BranchForm(farm=farm),
        'open_branch_modal': f'editBranch{edited_branch.pk}' if bound_form and edited_branch else 'addBranchModal' if bound_form else ''}


def branch_page(request, farm):
    json_request = 'application/json' in request.headers.get('Accept', '')
    if request.method != 'POST':
        context = branch_context(request, farm)
        if json_request:
            return JsonResponse({'html': render_to_string('includes/farm_branch_list.html', context, request=request)})
        return render(request, 'farm_branches.html', context)

    branch = None
    form = None
    error = None
    with transaction.atomic():
        # Serialize duplicate creates and edits/deletes for this owner's farm.
        farm = Farm.objects.select_for_update().get(pk=farm.pk, owner=request.user)
        action = request.POST.get('action', 'save')
        branch_id = request.POST.get('branch_id', '').strip()
        if branch_id:
            if not branch_id.isdigit():
                return JsonResponse({'error': 'The original farm cannot be deleted through branch management.'}, status=400) if json_request else render(request, 'farm_branches.html', branch_context(request, farm), status=400)
            branch = get_object_or_404(Branch, pk=branch_id, farm=farm)
        if action == 'delete':
            if not branch:
                error = 'Select an additional branch to delete. The original farm cannot be deleted here.'
            elif any(getattr(branch, relation.get_accessor_name()).exists() for relation in Branch._meta.related_objects):
                error = 'This branch has linked records. Deactivate it instead to preserve its flock, inventory and financial history.'
            else:
                branch.delete()
                message = 'Branch deleted successfully!'
        elif action == 'save':
            form = BranchForm(request.POST, farm=farm, branch=branch)
            if form.is_valid():
                values = form.cleaned_data.copy()
                values['name'] = values.pop('branch_name')
                if branch:
                    for name, value in values.items():
                        setattr(branch, name, value)
                    branch.save()  # Retain existing flock deactivation behavior.
                    message = 'Branch updated successfully!'
                else:
                    Branch.objects.create(farm=farm, **values)
                    message = 'Branch added successfully!'
            else:
                error = 'Please correct the branch information and try again.'
        else:
            error = 'Invalid branch action.'

        if error:
            if json_request:
                return JsonResponse({'error': error, 'errors': form.errors.get_json_data() if form is not None else {}}, status=400)
            messages.warning(request, error)
            return render(request, 'farm_branches.html', branch_context(request, farm, bound_form=form, edited_branch=branch))

        if json_request:
            query = '' if not branch_id else request.POST.get('q', '')
            context = branch_context(request, farm, query=query)
            return JsonResponse({'message': message, 'query': query,
                'html': render_to_string('includes/farm_branch_list.html', context, request=request)})
        messages.success(request, message)
        return redirect('farm_branches')
