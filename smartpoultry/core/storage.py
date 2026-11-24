"""Keep uploaded files in the database.

Render's disk is temporary: every redeploy deletes files written to MEDIA_ROOT, which
lost saved rooster photos (alpha test DEF-06). The PostgreSQL database is kept across
deploys, so uploads are stored there instead. Files are read through ``field.open()``
and served by views, so no public media URL is needed.
"""
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class DatabaseStorage(Storage):
    @staticmethod
    def _files():
        from .models import StoredFile
        return StoredFile.objects

    def _open(self, name, mode='rb'):
        row = self._files().filter(name=name).only('content').first()
        if row is None:
            raise FileNotFoundError(f'No stored file named {name!r}.')
        return ContentFile(bytes(row.content), name=name)

    def _save(self, name, content):
        if hasattr(content, 'seek'):
            content.seek(0)
        data = b''.join(content.chunks()) if hasattr(content, 'chunks') else content.read()
        self._files().create(name=name, content=data, size=len(data))
        return name

    def exists(self, name):
        return self._files().filter(name=name).exists()

    def delete(self, name):
        self._files().filter(name=name).delete()

    def size(self, name):
        row = self._files().filter(name=name).only('size').first()
        if row is None:
            raise FileNotFoundError(f'No stored file named {name!r}.')
        return row.size

    def url(self, name):
        # Photos are served only to their owner through rooster_estimate_photo.
        raise NotImplementedError('Stored files are served by the application views.')
