"""Shared checks for values that arrive in requests."""
from datetime import date

from django import forms
from django.utils import timezone
from rest_framework import serializers

EARLIEST_RECORD = date(2000, 1, 1)


def is_record_id(value):
    """True for text that can be a database ID. str.isdigit alone also accepts characters such as "²"."""
    text = str(value or '')
    return text.isascii() and text.isdigit() and len(text) <= 18


def record_date_error(value, current=None):
    """Explain why a record date is not acceptable. An unchanged date on an older record is left alone."""
    if value is None or value == current:
        return ''
    if value > timezone.localdate():
        return 'The date cannot be in the future. Records cannot be entered in advance.'
    if value < EARLIEST_RECORD:
        return 'Enter a date from the year 2000 onward.'
    return ''


class RecordDateMixin:
    """Serializer check: records describe things that have already happened."""

    def validate_date(self, value):
        error = record_date_error(value, getattr(self.instance, 'date', None))
        if error:
            raise serializers.ValidationError(error)
        return value


class RecordDateFormMixin:
    """The same check for pages that use Django forms."""

    def clean_date(self):
        value = self.cleaned_data['date']
        error = record_date_error(value, self.instance.date if self.instance.pk else None)
        if error:
            raise forms.ValidationError(error)
        return value
