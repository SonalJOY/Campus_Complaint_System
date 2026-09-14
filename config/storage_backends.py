"""
Custom Storage Backend for Supabase Private Storage Integration.
Enables Django to securely store and retrieve complaint attachment photos from Supabase Storage
using private, access-controlled buckets with signed time-limited URLs (TTL) and authenticated API transfers.
"""

import os
import mimetypes
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from django.core.files.storage import Storage
from django.core.files.base import ContentFile
from django.utils.deconstruct import deconstructible


@deconstructible
class SupabaseStorage(Storage):
    """
    Secure Storage adapter that uploads files to a private Supabase Storage Bucket
    via Supabase REST API endpoints with signed URLs for access control.
    """

    def __init__(self, **kwargs):
        raw_url = kwargs.get('supabase_url') if 'supabase_url' in kwargs else os.environ.get('SUPABASE_URL', '')
        # Normalize base URL: strip trailing slashes, /rest/v1, /storage/v1 if included
        import re
        clean_url = (raw_url or '').rstrip('/')
        clean_url = re.sub(r'/(rest|storage)(/v\d+)?/?$', '', clean_url)
        self.supabase_url = clean_url

        self.supabase_key = kwargs.get('supabase_key') if 'supabase_key' in kwargs else os.environ.get('SUPABASE_KEY', '')
        self.bucket_name = kwargs.get('bucket_name') or os.environ.get('SUPABASE_BUCKET', 'complaint-attachments')

        
        # Privacy & Access Control Settings:
        # Default is False (Private Bucket with Signed Time-Limited Access URLs)
        self.is_public = kwargs.get(
            'is_public',
            os.environ.get('SUPABASE_STORAGE_IS_PUBLIC', 'False').lower() in ('true', '1', 't')
        )
        # Default Signed URL validity: 3600 seconds (1 hour)
        self.signed_url_expires_in = int(
            kwargs.get('signed_url_expires_in') or os.environ.get('SUPABASE_SIGNED_URL_EXPIRY', '3600')
        )
        
        self.headers = {
            'apikey': self.supabase_key,
            'Authorization': f'Bearer {self.supabase_key}',
        }

        # Resilient HTTP session with connection pooling and retries
        self.session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            raise_on_status=False
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)

    def _get_object_url(self, name):
        clean_name = name.lstrip('/')
        return f"{self.supabase_url}/storage/v1/object/{self.bucket_name}/{clean_name}"

    def _get_public_url(self, name):
        clean_name = name.lstrip('/')
        return f"{self.supabase_url}/storage/v1/object/public/{self.bucket_name}/{clean_name}"

    def _get_sign_url(self, name):
        clean_name = name.lstrip('/')
        return f"{self.supabase_url}/storage/v1/object/sign/{self.bucket_name}/{clean_name}"

    def _save(self, name, content):
        """
        Uploads file content directly to private Supabase Storage bucket.
        """
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables are required for SupabaseStorage.")

        content.seek(0)
        file_bytes = content.read()
        content_type, _ = mimetypes.guess_type(name)
        content_type = content_type or 'application/octet-stream'

        upload_headers = dict(self.headers)
        upload_headers['Content-Type'] = content_type
        upload_headers['x-upsert'] = 'true'

        url = self._get_object_url(name)
        response = self.session.post(url, headers=upload_headers, data=file_bytes, timeout=30)
        
        if response.status_code not in (200, 201):
            # Fallback to PUT if file exists
            put_response = self.session.put(url, headers=upload_headers, data=file_bytes, timeout=30)
            if put_response.status_code not in (200, 201):
                raise IOError(f"Failed to upload to Supabase Storage: {response.text} / {put_response.text}")

        return name

    def _open(self, name, mode='rb'):
        """
        Downloads file content from private Supabase Storage using authenticated GET request.
        """
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables are required for SupabaseStorage.")

        url = self._get_object_url(name)
        response = self.session.get(url, headers=self.headers, timeout=30)
        if response.status_code == 200:
            return ContentFile(response.content, name=name)
        raise FileNotFoundError(f"File '{name}' could not be found in Supabase Storage ({response.status_code}).")

    def exists(self, name):
        """
        Checks whether the file already exists in the private bucket using authenticated range request.
        """
        if not self.supabase_url or not self.supabase_key:
            return False

        url = self._get_object_url(name)
        try:
            # Check existence via authenticated 1-byte GET
            headers = dict(self.headers)
            headers['Range'] = 'bytes=0-0'
            response = self.session.get(url, headers=headers, timeout=10)
            return response.status_code in (200, 206)
        except Exception:
            return False

    def get_signed_url(self, name, expires_in=None):
        """
        Generates a secure, temporary, time-limited signed URL for viewing private files.
        """
        if not self.supabase_url or not self.supabase_key:
            return f"/media/{name}"

        clean_name = name.lstrip('/')
        expires = expires_in or self.signed_url_expires_in
        sign_url = self._get_sign_url(clean_name)
        
        try:
            response = self.session.post(
                sign_url,
                headers=self.headers,
                json={"expiresIn": expires},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                signed_path = data.get("signedURL") or data.get("signedUrl")
                if signed_path:
                    if signed_path.startswith("http"):
                        return signed_path
                    if not signed_path.startswith("/storage/v1"):
                        signed_path = f"/storage/v1{signed_path}"
                    return f"{self.supabase_url}{signed_path}"
        except Exception:
            pass

        return self._get_object_url(clean_name)

    def url(self, name):
        """
        Returns the appropriate URL for serving the file to end users.
        - Private Bucket (Default): Generates a secure, short-lived signed URL.
        - Public Bucket (if is_public=True): Generates static public URL.
        """
        if not self.supabase_url:
            return f"/media/{name}"
        
        if self.is_public:
            return self._get_public_url(name)
        
        return self.get_signed_url(name)

    def delete(self, name):
        """
        Deletes the file from Supabase Storage.
        """
        if not self.supabase_url or not self.supabase_key:
            return

        clean_name = name.lstrip('/')
        url = f"{self.supabase_url}/storage/v1/object/{self.bucket_name}"
        payload = {"prefixes": [clean_name]}
        try:
            self.session.delete(url, headers=self.headers, json=payload, timeout=10)
        except Exception:
            pass
