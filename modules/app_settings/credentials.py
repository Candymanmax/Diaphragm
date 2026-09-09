from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import uuid

from PySide6.QtCore import QObject, QSettings, Signal

from modules.app_settings.models import CredentialStoreError

class CredentialStore:
    """Small keyring-backed store that never exposes credentials in settings."""

    SERVICE_NAME = "Diaphragm"
    HUGGINGFACE_KEY = "huggingface-token"

    def __init__(self, backend=None):
        self._backend = backend

    def _keyring(self):
        if self._backend is not None:
            return self._backend

        try:
            import keyring
        except ImportError as error:
            raise CredentialStoreError(
                "Secure credential support is unavailable. Install keyring."
            ) from error

        return keyring

    def token(self):
        try:
            return self._keyring().get_password(
                self.SERVICE_NAME,
                self.HUGGINGFACE_KEY,
            )
        except Exception as error:
            raise CredentialStoreError(
                "Windows Credential Manager could not be read."
            ) from error

    def has_token(self):
        return bool(self.token())

    def set_token(self, token):
        token = str(token).strip()

        if not token:
            raise CredentialStoreError("Enter a Hugging Face token.")

        try:
            self._keyring().set_password(
                self.SERVICE_NAME,
                self.HUGGINGFACE_KEY,
                token,
            )
        except Exception as error:
            raise CredentialStoreError(
                "Windows Credential Manager could not save the token."
            ) from error

    def clear_token(self):
        backend = self._keyring()

        try:
            backend.delete_password(
                self.SERVICE_NAME,
                self.HUGGINGFACE_KEY,
            )
        except Exception as error:
            # Keyring backends use different missing-entry exceptions.
            if "not found" not in str(error).lower():
                raise CredentialStoreError(
                    "Windows Credential Manager could not clear the token."
                ) from error
