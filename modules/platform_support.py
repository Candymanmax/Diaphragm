"""Platform names shared by desktop prompts and backend errors."""

import sys


def credential_store_name():
    if sys.platform == "darwin":
        return "macOS Keychain"
    if sys.platform == "win32":
        return "Windows Credential Manager"
    return "the system keyring"


def trash_name():
    return "Recycle Bin" if sys.platform == "win32" else "Trash"
