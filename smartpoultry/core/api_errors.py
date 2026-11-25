"""API answers for rules that the models check while saving."""
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from rest_framework import exceptions
from rest_framework.views import exception_handler


def api_exception_handler(error, context):
    """Two people can submit at the same moment, so a model may refuse what the form had already accepted."""
    if isinstance(error, ValidationError):
        error = exceptions.ValidationError(error.message_dict if hasattr(error, 'error_dict') else error.messages)
    elif isinstance(error, ObjectDoesNotExist):
        error = exceptions.NotFound('This record is no longer available.')
    return exception_handler(error, context)
