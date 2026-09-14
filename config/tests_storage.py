"""
Unit tests for SupabaseStorage private bucket adapter.
Verifies uploads, downloads, existence checks, signed URL generation, deletions, and error handling.
"""

from unittest.mock import patch, MagicMock
from django.test import SimpleTestCase
from django.core.files.base import ContentFile
from config.storage_backends import SupabaseStorage


class SupabaseStorageTests(SimpleTestCase):
    def setUp(self):
        self.storage = SupabaseStorage(
            supabase_url="https://testproject.supabase.co",
            supabase_key="test-api-key-12345",
            bucket_name="test-complaints",
            is_public=False,
            signed_url_expires_in=1800
        )

    def test_save_upload_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 201
        self.storage.session.post = MagicMock(return_value=mock_response)

        content = ContentFile(b"test image binary data", name="complaints/photo.jpg")
        saved_name = self.storage._save("complaints/photo.jpg", content)

        self.assertEqual(saved_name, "complaints/photo.jpg")
        self.storage.session.post.assert_called_once()
        call_args = self.storage.session.post.call_args
        self.assertIn("https://testproject.supabase.co/storage/v1/object/test-complaints/complaints/photo.jpg", call_args[0][0])
        self.assertEqual(call_args[1]['headers']['apikey'], "test-api-key-12345")
        self.assertEqual(call_args[1]['headers']['Authorization'], "Bearer test-api-key-12345")
        self.assertEqual(call_args[1]['headers']['Content-Type'], "image/jpeg")

    def test_open_download_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"downloaded file bytes"
        self.storage.session.get = MagicMock(return_value=mock_response)

        downloaded = self.storage._open("complaints/photo.jpg")
        self.assertEqual(downloaded.read(), b"downloaded file bytes")
        self.storage.session.get.assert_called_once()

    def test_open_download_not_found(self):
        mock_response = MagicMock()
        mock_response.status_code = 404
        self.storage.session.get = MagicMock(return_value=mock_response)

        with self.assertRaises(FileNotFoundError):
            self.storage._open("complaints/nonexistent.jpg")

    def test_exists_true(self):
        mock_response = MagicMock()
        mock_response.status_code = 206
        self.storage.session.get = MagicMock(return_value=mock_response)

        self.assertTrue(self.storage.exists("complaints/photo.jpg"))

    def test_exists_false(self):
        mock_response = MagicMock()
        mock_response.status_code = 404
        self.storage.session.get = MagicMock(return_value=mock_response)

        self.assertFalse(self.storage.exists("complaints/nonexistent.jpg"))

    def test_private_signed_url_generation(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "signedURL": "/storage/v1/object/sign/test-complaints/complaints/photo.jpg?token=mock_jwt_token_123"
        }
        self.storage.session.post = MagicMock(return_value=mock_response)

        url = self.storage.url("complaints/photo.jpg")
        self.assertEqual(
            url,
            "https://testproject.supabase.co/storage/v1/object/sign/test-complaints/complaints/photo.jpg?token=mock_jwt_token_123"
        )
        self.storage.session.post.assert_called_once()
        self.assertEqual(self.storage.session.post.call_args[1]['json']['expiresIn'], 1800)

    def test_public_url_generation_when_explicitly_configured(self):
        public_storage = SupabaseStorage(
            supabase_url="https://testproject.supabase.co",
            supabase_key="test-api-key-12345",
            bucket_name="test-complaints",
            is_public=True
        )
        url = public_storage.url("complaints/photo.jpg")
        self.assertEqual(
            url,
            "https://testproject.supabase.co/storage/v1/object/public/test-complaints/complaints/photo.jpg"
        )

    def test_delete_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        self.storage.session.delete = MagicMock(return_value=mock_response)

        self.storage.delete("complaints/photo.jpg")
        self.storage.session.delete.assert_called_once()
        self.assertEqual(self.storage.session.delete.call_args[1]['json'], {"prefixes": ["complaints/photo.jpg"]})

    def test_offline_local_fallback(self):
        offline_storage = SupabaseStorage(supabase_url="", supabase_key="")
        self.assertEqual(offline_storage.url("complaints/photo.jpg"), "/media/complaints/photo.jpg")
        self.assertFalse(offline_storage.exists("complaints/photo.jpg"))
