from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class RegistrationPasswordTests(TestCase):
    def details(self, password):
        return {'username': 'new-owner', 'email': 'owner@example.com', 'password': password, 'password2': password,
            'question_one': 'school_trip', 'question_two': 'stuffed_toy',
            'answer_one': 'Private mountain trip', 'answer_two': 'Purple toy dragon'}

    def test_each_missing_rule_is_rejected_on_server(self):
        examples = [('Ab1!', 'too short'), ('lowercase12!', 'uppercase letter'),
            ('UPPERCASE12!', 'lowercase letter'), ('Mixedletters!', 'number'), ('Mixedletters12', 'special symbol')]
        for password, expected in examples:
            with self.subTest(password=password):
                response = self.client.post(reverse('register'), self.details(password))
                self.assertContains(response, expected)
                self.assertFalse(get_user_model().objects.filter(username='new-owner').exists())

    def test_password_confirmation_must_match(self):
        response = self.client.post(reverse('register'), {**self.details('Strong-secret!79'), 'password2': 'Different-secret!79'})
        self.assertContains(response, 'Passwords do not match.')
        self.assertFalse(get_user_model().objects.filter(username='new-owner').exists())

    def test_valid_password_registers_and_returns_to_login(self):
        response = self.client.post(reverse('register'), self.details('Strong-secret!79'), follow=True)
        self.assertContains(response, 'Account Created Successfully!')
        self.assertTrue(get_user_model().objects.get(username='new-owner').check_password('Strong-secret!79'))
        self.assertNotIn('_auth_user_id', self.client.session)
