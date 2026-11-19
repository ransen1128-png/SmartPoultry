import re
import string

from django.core.exceptions import ValidationError


class PasswordComplexityValidator:
    """Composition rules for newly created or changed passwords."""
    def validate(self, password, user=None):
        errors = []
        if not re.search(r'[A-Z]', password):
            errors.append('Your password must include at least one uppercase letter (A-Z).')
        if not re.search(r'[a-z]', password):
            errors.append('Your password must include at least one lowercase letter (a-z).')
        if not re.search(r'[0-9]', password):
            errors.append('Your password must include at least one number (0-9).')
        if not any(character in string.punctuation for character in password):
            errors.append('Your password must include at least one special symbol (e.g., !, @, #, $).')
        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return 'Your password must include an uppercase letter (A-Z), a lowercase letter (a-z), a number (0-9), and a special symbol (e.g., !, @, #, $).'
