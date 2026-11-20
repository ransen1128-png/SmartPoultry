# Password reset email setup

The default recovery method is now **questions**, which needs no domain or
email provider. New registrations save two distinct questions and hashed answers.
Both answers must match before the password form is accessible. Five incorrect
attempts lock question verification for 15 minutes, persisted in the database.
A verified reset session lasts ten minutes and is invalidated by a password
change. Administrators must also enter the correct answers when resetting an
account that has recovery questions; saved answers are never displayed.

The public administrator-help option has been removed from password recovery,
including its request endpoint and error-message references. Existing accounts
have no invented recovery answers. Previously recorded requests remain available
to administrators in their request history.

To enable the optional email flow below, set `PASSWORD_RESET_METHOD=email` in
both `.env` and Render's Environment. Use `questions` for the default free flow.
Apply migrations on deployment:
`python smartpoultry/manage.py migrate`. Render's current start command already
runs migrations.

SmartPoultry uses Django's password reset tokens and the Resend HTTPS email API.
The forgot-password page accepts an email only; changing a password requires the
single-use emailed link. Links expire after 30 minutes. Resetting does not sign
the account in automatically. Disabled accounts do not receive reset links.

## Connect real email delivery

1. Create an account at https://resend.com and add a domain you control.
2. Add the DNS records Resend provides and wait for the sender domain to verify.
3. Create a sending API key. Keep it private.
4. Set these values in the desktop `.env` and Render's web service Environment:

   ```text
   RESEND_API_KEY=<your private sending API key>
   DEFAULT_FROM_EMAIL=SmartPoultry <noreply@your-verified-domain.com>
   ```

5. Restart localhost. On Render, save the environment variables and deploy the
   updated code. Keep the existing production SECRET_KEY stable across deploys.
6. Request a reset for your own registered email, open the received link, set a
   new password, then log in. Check spam if the email is not in the inbox.

The example sender is a placeholder: use your real verified domain. Resend's
`onboarding@resend.dev` test sender delivers only to the Resend account owner's
email; it cannot be used for arbitrary registered users. Provider quotas apply.
An `onrender.com` hostname does not grant DNS control for verifying a sender.

Render blocks standard SMTP ports on free web services, so this integration
sends over HTTPS port 443 and requires no email SDK or extra dependencies.
See [Render free service limitations](https://render.com/docs/free) and
[Resend email API](https://resend.com/docs/api-reference/emails/send-email).

`PASSWORD_RESET_BASE_URL` can override the site origin, for example
`https://smartpoultry-l3qo.onrender.com`. Render automatically uses its
RENDER_EXTERNAL_HOSTNAME when no override is set. Leave the override unset on
localhost so locally issued links point back to localhost.

## Delivery state and diagnostics

Without a key and sender, the page explicitly says reset email is unavailable;
it never changes a password directly. Delivery failures log a sanitized
`Password reset email failed` entry. Check Resend's delivery dashboard for
accepted, delivered, bounced or rejected messages. API acceptance is not proof
of inbox delivery. Public confirmations do not reveal whether an email exists.

Repeated requests for the same email are limited to one send per minute using
Django's cache. The default in-memory cache is per worker; use a shared Django
cache when scaling beyond the current single worker.

For local development only, `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend`
prints links in the terminal instead of sending email. This mode must not be
used on Render or advertised as real delivery. Automated tests use an isolated
in-memory email backend and database; they do not send real reset emails.
