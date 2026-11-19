"""Recovery answers are hashed secrets; never reveal the stored answers."""
import unicodedata
from datetime import timedelta

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.core import signing
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters

from .models import AccountRecovery, PasswordResetRequest
from .password_reset import ResetPasswordForm

QUESTIONS = [
    ('school_trip', 'Where was your most memorable school field trip?'),
    ('stuffed_toy', 'What was the name of your first stuffed toy?'),
    ('college', 'Which college did you apply to but never attend?'),
    ('teacher', 'What was your eighth-grade mathematics teacher\'s full name?'),
    ('childhood_place', 'What private childhood place do you remember most?'),
    ('secret_phrase', 'What unique recovery phrase did you choose for SmartPoultry?'),
]


def normalize_answer(value):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


class RecoverySetupForm(forms.Form):
    question_one = forms.ChoiceField(label='Recovery Question 1', choices=QUESTIONS)
    answer_one = forms.CharField(label='Answer 1', min_length=6, max_length=200, widget=forms.PasswordInput)
    question_two = forms.ChoiceField(label='Recovery Question 2', choices=QUESTIONS)
    answer_two = forms.CharField(label='Answer 2', min_length=6, max_length=200, widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['question_two'].initial = QUESTIONS[1][0]
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-select' if isinstance(field, forms.ChoiceField) else 'form-control'
            if isinstance(field.widget, forms.PasswordInput):
                field.widget.attrs['autocomplete'] = 'off'

    def clean(self):
        data = super().clean()
        if data.get('question_one') == data.get('question_two'):
            raise forms.ValidationError('Choose two different recovery questions.')
        one, two = normalize_answer(data.get('answer_one', '')), normalize_answer(data.get('answer_two', ''))
        if one and one == two:
            raise forms.ValidationError('Use a different answer for each question.')
        for name, answer in (('answer_one', one), ('answer_two', two)):
            if answer and (len(answer) < 6 or answer.isdigit()):
                self.add_error(name, 'Use at least six characters, not only numbers.')
        return data

    def save(self, user):
        return AccountRecovery.objects.create(
            user=user,
            question_one=self.cleaned_data['question_one'], question_two=self.cleaned_data['question_two'],
            answer_one_hash=make_password(normalize_answer(self.cleaned_data['answer_one'])),
            answer_two_hash=make_password(normalize_answer(self.cleaned_data['answer_two'])),
        )


def verify_answers(profile, one, two):
    """Caller must hold a row lock in an atomic transaction."""
    now = timezone.now()
    if profile.locked_until and profile.locked_until > now:
        return False
    if profile.locked_until:
        profile.failed_attempts = 0
        profile.locked_until = None
    first = check_password(normalize_answer(one), profile.answer_one_hash)
    second = check_password(normalize_answer(two), profile.answer_two_hash)
    if first and second:
        profile.failed_attempts = 0
        profile.locked_until = None
    else:
        profile.failed_attempts += 1
        if profile.failed_attempts >= 5:
            profile.locked_until = now + timedelta(minutes=15)
    profile.save(update_fields=['failed_attempts', 'locked_until'])
    return first and second


def question_labels(profile):
    choices = dict(QUESTIONS)
    return [choices.get(profile.question_one, QUESTIONS[0][1]), choices.get(profile.question_two, QUESTIONS[1][1])] if profile else [QUESTIONS[0][1], QUESTIONS[1][1]]


@never_cache
@sensitive_post_parameters('answer_one', 'answer_two')
def answer_questions(request):
    from django.db import transaction
    from django.core.cache import cache
    from django.utils.crypto import salted_hmac
    challenge = request.session.get('recovery_challenge', {})
    if not challenge or challenge.get('expires', 0) < timezone.now().timestamp():
        return redirect('forgot_password')
    email = challenge.get('email', '')
    # Match username as well to disambiguate existing duplicate email addresses.
    user = get_user_model().objects.filter(
        email__iexact=email, username=challenge.get('username', ''), is_active=True, is_active_user=True,
    ).first()
    profile = AccountRecovery.objects.filter(user=user).first() if user else None
    error = None
    if request.method == 'POST':
        request.session.pop('recovery_grant', None)
        key = 'recovery-attempt:' + salted_hmac('recovery', email.casefold() + '\0' + challenge.get('username', '')).hexdigest()
        if not cache.add(key, True, timeout=2):
            error = 'Please wait a moment before trying again.'
        else:
            verified = False
            if profile:
                with transaction.atomic():
                    profile = AccountRecovery.objects.select_for_update().get(pk=profile.pk)
                    verified = verify_answers(profile, request.POST.get('answer_one', '')[:200], request.POST.get('answer_two', '')[:200])
            if verified:
                request.session.cycle_key()
                request.session['recovery_grant'] = signing.dumps({
                    'user': user.pk, 'password': user.get_session_auth_hash(),
                    'answers': profile.answer_one_hash + profile.answer_two_hash,
                }, salt='recovery-password-change')
                request.session.pop('recovery_challenge', None)
                return redirect('question_password_reset')
            error = 'The answers could not be verified. After five incorrect attempts, wait 15 minutes or request administrator help.'
    return render(request, 'recovery_questions.html', {'question_labels': question_labels(profile), 'error': error})


@never_cache
@sensitive_post_parameters('new_password1', 'new_password2')
def change_password(request):
    try:
        grant = signing.loads(request.session.get('recovery_grant', ''), salt='recovery-password-change', max_age=600)
        user = get_user_model().objects.get(pk=grant['user'], is_active=True, is_active_user=True)
        profile = AccountRecovery.objects.get(user=user)
        if not constant_time_compare(grant['password'], user.get_session_auth_hash()) or not constant_time_compare(grant['answers'], profile.answer_one_hash + profile.answer_two_hash):
            raise signing.BadSignature()
    except (signing.BadSignature, KeyError, get_user_model().DoesNotExist, AccountRecovery.DoesNotExist):
        request.session.pop('recovery_grant', None)
        return render(request, 'password_reset_confirm.html', {'validlink': False})
    form = ResetPasswordForm(user, request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        from django.db import transaction
        with transaction.atomic():
            current = get_user_model().objects.select_for_update().get(pk=user.pk)
            if not constant_time_compare(grant['password'], current.get_session_auth_hash()):
                request.session.pop('recovery_grant', None)
                return render(request, 'password_reset_confirm.html', {'validlink': False})
            form.save()
            PasswordResetRequest.objects.filter(user=user, status='pending').update(status='resolved', resolved_at=timezone.now())
        request.session.pop('recovery_grant', None)
        request.session.cycle_key()
        return redirect('password_reset_complete')
    return render(request, 'password_reset_confirm.html', {'validlink': True, 'form': form})
