"""Transactional email over HTTPS, including on Render's free web services."""
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.exceptions import ImproperlyConfigured


class EmailDeliveryError(Exception):
    """A sanitized error: never include API keys, recipients or reset links."""


class ResendEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages or []:
            if not message.recipients():
                continue
            try:
                if not settings.RESEND_API_KEY or not message.from_email:
                    raise ImproperlyConfigured('Email API key and verified sender are required.')
                payload = {
                    'from': message.from_email,
                    'to': list(message.to),
                    'subject': message.subject,
                    'text': message.body,
                }
                for field in ('cc', 'bcc', 'reply_to'):
                    if getattr(message, field):
                        payload[field] = list(getattr(message, field))
                for content, mimetype in getattr(message, 'alternatives', []):
                    if mimetype == 'text/html':
                        payload['html'] = content
                request = Request(
                    'https://api.resend.com/emails',
                    data=json.dumps(payload).encode('utf-8'),
                    headers={
                        'Authorization': 'Bearer ' + settings.RESEND_API_KEY,
                        'Content-Type': 'application/json',
                        'User-Agent': 'SmartPoultry/1.0',
                    },
                    method='POST',
                )
                try:
                    with urlopen(request, timeout=settings.EMAIL_TIMEOUT) as response:
                        result = json.loads(response.read(65536))
                        if not isinstance(result, dict) or not result.get('id'):
                            raise EmailDeliveryError('Email service did not confirm acceptance.')
                except HTTPError as error:
                    raise EmailDeliveryError(f'Email service returned HTTP {error.code}.') from None
                except (URLError, OSError, ValueError) as error:
                    raise EmailDeliveryError('Email service could not be reached or returned an invalid response.') from None
                sent += 1
            except (EmailDeliveryError, ImproperlyConfigured):
                if not self.fail_silently:
                    raise
        return sent
