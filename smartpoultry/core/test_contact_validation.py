from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from accounts.serializers import UserProfileSerializer
from core.models import Farm


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ContactPhoneTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('contact-owner', 'contact@example.invalid', 'Secret!123')
        self.client.force_login(self.user)

    def test_invalid_farm_phone_is_rejected_without_creating_farm(self):
        for phone in ('0912345678', 'abcdefghijk', '0' * 21):
            with self.subTest(phone=phone):
                response = self.client.post('/farm/branches/', {
                    'farm_name':'Test Farm', 'farm_location':'Town', 'established_date':'2026-01-01',
                    'contact_email':'contact@example.invalid', 'contact_phone':phone,
                })
                self.assertContains(response, 'at least 11 digits')
                self.assertFalse(Farm.objects.filter(owner=self.user).exists())

    def test_eleven_digit_farm_phone_is_accepted(self):
        response = self.client.post('/farm/branches/', {
            'farm_name':'Test Farm', 'established_date':'2026-01-01',
            'contact_email':'contact@example.invalid', 'contact_phone':'09123456789',
        })
        self.assertEqual(response.status_code,302)
        self.assertEqual(Farm.objects.get(owner=self.user).contact_phone,'09123456789')

    def test_profile_rejects_short_phone_without_changing_account(self):
        response = self.client.post('/profile/', {'username':self.user.username,
            'email':self.user.email, 'phone':'123'})
        self.assertContains(response,'at least 11 digits')
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone,'')

    def test_api_validation_and_optional_phone(self):
        for phone,expected in [('123',False),('abcdefghijk',False),('09123456789',True),('0'*20,True),('',True)]:
            with self.subTest(phone=phone):
                serializer=UserProfileSerializer(self.user,data={'phone':phone},partial=True)
                self.assertEqual(serializer.is_valid(),expected,serializer.errors)
