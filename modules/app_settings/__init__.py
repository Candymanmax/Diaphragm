"""Typed application preferences, paths, migration, credentials, and logs."""

from modules.app_settings.credentials import CredentialStore
from modules.app_settings.diagnostics import DiagnosticLogStore
from modules.app_settings.migration import (
    MigrationReport,
    directory_size,
    file_sha256,
    migrate_directory_verified,
    migrate_library,
    migrate_model_cache,
)
from modules.app_settings.models import (
    APP_VERSION,
    LIBRARY_FOLDERS,
    PREFERENCES_SCHEMA_VERSION,
    RELEASES_URL,
    SUPPORTED_ACCENTS,
    AppPaths,
    AppPreferences,
    CredentialStoreError,
    PathMigrationError,
    SettingsError,
)
from modules.app_settings.repository import SettingsRepository

__all__ = (
    "APP_VERSION",
    "LIBRARY_FOLDERS",
    "PREFERENCES_SCHEMA_VERSION",
    "RELEASES_URL",
    "SUPPORTED_ACCENTS",
    "AppPaths",
    "AppPreferences",
    "CredentialStore",
    "CredentialStoreError",
    "DiagnosticLogStore",
    "MigrationReport",
    "PathMigrationError",
    "SettingsError",
    "SettingsRepository",
    "directory_size",
    "file_sha256",
    "migrate_directory_verified",
    "migrate_library",
    "migrate_model_cache",
)
