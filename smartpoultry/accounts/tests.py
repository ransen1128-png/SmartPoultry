from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from core.models import Farm
from django.core.management import call_command
from io import StringIO
import json


class AccountRetentionTests(TestCase):
    def setUp(self):
        self.User=get_user_model()
        self.owner=self.User.objects.create_user(username='retention-owner',password='RetentionTest123!')
        self.other=self.User.objects.create_user(username='retention-other',email='other@example.com',password='RetentionOther123!')
        self.client.force_login(self.owner)

    def test_regular_users_cannot_read_change_or_delete_other_accounts(self):
        url=reverse('user-detail',args=[self.other.pk])
        self.assertEqual(self.client.get(url).status_code,404)
        self.assertEqual(self.client.patch(url,{'email':'changed@example.com'},content_type='application/json').status_code,404)
        self.assertEqual(self.client.delete(url).status_code,403)
        self.other.refresh_from_db()
        self.assertEqual(self.other.email,'other@example.com')
        self.assertTrue(self.other.check_password('RetentionOther123!'))
        data=self.client.get(reverse('user-list')).json()['results']
        self.assertEqual([row['id'] for row in data],[self.owner.pk])

    def test_regular_users_cannot_reassign_farm_change_role_or_deactivate_self(self):
        result=self.client.patch(reverse('user-detail',args=[self.owner.pk]),{'role':'admin','farm':9999,'is_active_user':False},content_type='application/json')
        self.assertEqual(result.status_code,200,result.content)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.role,'staff')
        self.assertIsNone(self.owner.farm_id)
        self.assertTrue(self.owner.is_active_user)
        self.assertEqual(self.client.delete(reverse('user-detail',args=[self.owner.pk])).status_code,403)

    def test_deleting_a_farm_preserves_member_account_and_password(self):
        farm=Farm.objects.create(owner=self.owner,name='Retained farm',location='Town',established_date=date(2026,1,1),contact_email='owner@example.com',contact_phone='123')
        self.other.farm=farm;self.other.save()
        farm.delete()
        self.other.refresh_from_db()
        self.assertIsNone(self.other.farm_id)
        self.assertTrue(self.other.is_active)
        self.assertTrue(self.other.check_password('RetentionOther123!'))

    def test_staff_cannot_delete_self_or_modify_superusers(self):
        self.owner.is_staff=True;self.owner.save()
        self.other.is_superuser=True;self.other.save()
        self.assertEqual(self.client.delete(reverse('user-detail',args=[self.owner.pk])).status_code,403)
        self.assertEqual(self.client.delete(reverse('user-detail',args=[self.other.pk])).status_code,403)
        self.assertEqual(self.client.patch(reverse('user-detail',args=[self.other.pk]),{'email':'changed@example.com'},content_type='application/json').status_code,403)

    def test_storage_inspection_is_read_only_and_does_not_output_password_hashes(self):
        before=self.User.objects.count();password_hash=self.other.password
        output=StringIO()
        call_command('inspect_account_storage',email=self.other.email,stdout=output)
        report=json.loads(output.getvalue())
        self.assertTrue(report['read_only'])
        self.assertEqual(report['matching_accounts'][0]['id'],self.other.pk)
        self.assertNotIn(password_hash,output.getvalue())
        self.other.refresh_from_db()
        self.assertEqual(self.other.password,password_hash)
        self.assertEqual(self.User.objects.count(),before)
