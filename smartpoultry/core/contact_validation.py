import re


PHONE_ERROR = 'Enter a contact phone number with at least 11 digits (numbers only, up to 20 digits).'


def valid_contact_phone(value):
    return bool(re.fullmatch(r'[0-9]{11,20}', value))
