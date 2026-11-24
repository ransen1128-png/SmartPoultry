"""Regression tests for the fixes made after alpha testing (DEF-02, DEF-06, DEF-08)."""
import shutil
import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from core.models import AuditEvent, Branch, Farm, RoosterAgeEstimate, StoredFile
from core.storage import DatabaseStorage
from flocks.models import Flock


def png_bytes():
    buffer = BytesIO()
    Image.new('RGB', (8, 8), (200, 120, 60)).save(buffer, format='PNG')
    return buffer.getvalue()


class DatabaseStorageTests(TestCase):
    """DEF-06: uploads are kept in the database, which survives Render redeploys."""

    def setUp(self):
        # Point MEDIA_ROOT at an empty folder: nothing may depend on files on disk.
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)
        media = override_settings(MEDIA_ROOT=self.folder)
        media.enable()
        self.addCleanup(media.disable)

    def test_default_storage_is_the_database(self):
        self.assertIsInstance(default_storage._wrapped if hasattr(default_storage, '_wrapped') else default_storage, DatabaseStorage)

    def test_save_open_exists_size_delete(self):
        storage = DatabaseStorage()
        name = storage.save('rooster_age_estimates/2026/11/spur.jpg', ContentFile(b'photo-bytes'))
        self.assertTrue(storage.exists(name))
        self.assertEqual(storage.size(name), 11)
        with storage.open(name) as stream:
            self.assertEqual(stream.read(), b'photo-bytes')
        second = storage.save('rooster_age_estimates/2026/11/spur.jpg', ContentFile(b'other'))
        self.assertNotEqual(name, second)
        storage.delete(name)
        self.assertFalse(storage.exists(name))
        with self.assertRaises(FileNotFoundError):
            storage.open(name)

    def test_rooster_photo_is_served_from_the_database(self):
        user = get_user_model().objects.create_user('photo-owner', email='photo@example.com', password='Secret!123')
        content = png_bytes()
        record = RoosterAgeEstimate.objects.create(user=user, photo=SimpleUploadedFile('spur.png', content), photo_name='spur.png')
        self.assertTrue(StoredFile.objects.filter(name=record.photo.name).exists())
        shutil.rmtree(self.folder, ignore_errors=True)  # as after a redeploy: the disk is empty
        self.client.force_login(user)
        response = self.client.get(reverse('rooster_estimate_photo', args=[record.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), content)

    def test_other_accounts_cannot_open_the_photo(self):
        owner = get_user_model().objects.create_user('photo-owner2', email='p2@example.com', password='Secret!123')
        other = get_user_model().objects.create_user('photo-other', email='p3@example.com', password='Secret!123')
        record = RoosterAgeEstimate.objects.create(user=owner, photo=SimpleUploadedFile('spur.png', png_bytes()), photo_name='spur.png')
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('rooster_estimate_photo', args=[record.pk])).status_code, 404)


class NotesChangeHistoryTests(TestCase):
    """DEF-02: correcting only the notes of a record appears in Change History."""

    def test_flock_notes_correction_is_recorded(self):
        user = get_user_model().objects.create_user('notes-owner', email='notes@example.com', password='Secret!123')
        farm = Farm.objects.create(owner=user, name='Notes Farm', location='Argao', established_date='2026-01-01',
                                   contact_email='notes@example.com', contact_phone='09170000000')
        branch = Branch.objects.create(farm=farm, name='Notes Branch')
        flock = Flock.objects.create(user=user, branch=branch, flock_id='01', breed='layers', quantity=10)
        self.client.force_login(user)
        response = self.client.patch(f'/api/flocks/{flock.pk}/', {'notes': 'Moved to pen 2', 'correction_reason': 'Pen changed'},
                                     content_type='application/json')
        self.assertEqual(response.status_code, 200)
        event = AuditEvent.objects.filter(object_type='flocks.Flock', object_id=flock.pk, action='updated').latest('pk')
        self.assertEqual(event.before.get('notes'), '')
        self.assertEqual(event.after.get('notes'), 'Moved to pen 2')
        self.assertEqual(event.reason, 'Pen changed')
        page = self.client.get(reverse('activity_history'))
        self.assertContains(page, 'Moved to pen 2')


class MobileMenuTests(TestCase):
    """DEF-08: phones get a Menu button instead of the full menu above every page."""

    def test_owner_pages_have_the_mobile_menu_button(self):
        user = get_user_model().objects.create_user('menu-owner', email='menu@example.com', password='Secret!123')
        self.client.force_login(user)
        html = self.client.get(reverse('dashboard')).content.decode()
        self.assertIn('id="sidebarMobileToggle"', html)
        self.assertIn('aria-controls="sidebarNav"', html)
        self.assertIn('id="sidebarNav"', html)


class PhilippineDateTests(TestCase):
    """Early-morning farm records must use the Philippine date, not the UTC date."""

    def test_today_is_the_philippine_date_before_eight_in_the_morning(self):
        from datetime import date, datetime, timezone as dt_timezone
        from unittest import mock
        from django.utils import timezone
        early_morning = datetime(2026, 11, 24, 16, 6, tzinfo=dt_timezone.utc)  # 12:06 AM on Nov 25 in Argao
        with mock.patch('django.utils.timezone.now', return_value=early_morning):
            self.assertEqual(timezone.localdate(), date(2026, 11, 25))
