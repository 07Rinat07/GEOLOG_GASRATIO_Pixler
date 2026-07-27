from __future__ import annotations

from ctypes import POINTER, Structure, byref, c_byte, c_void_p, cast, sizeof, string_at
from ctypes import wintypes
from dataclasses import dataclass
import os
from typing import Protocol

from geoworkbench.importers.witsml1411.models import Witsml1411Credentials


class WitsmlCredentialStoreError(RuntimeError):
    pass


class WitsmlCredentialStore(Protocol):
    def load(self, credential_id: str) -> Witsml1411Credentials | None: ...
    def save(self, credential_id: str, credentials: Witsml1411Credentials) -> None: ...
    def delete(self, credential_id: str) -> None: ...


@dataclass(slots=True)
class InMemoryWitsmlCredentialStore:
    _items: dict[str, Witsml1411Credentials]

    def __init__(self) -> None:
        self._items = {}

    def load(self, credential_id: str) -> Witsml1411Credentials | None:
        return self._items.get(credential_id)

    def save(self, credential_id: str, credentials: Witsml1411Credentials) -> None:
        if not credential_id.strip():
            raise ValueError("credential_id must be non-empty")
        self._items[credential_id] = credentials

    def delete(self, credential_id: str) -> None:
        self._items.pop(credential_id, None)


if os.name == "nt":
    import ctypes

    class _FILETIME(Structure):
        _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

    class _CREDENTIALW(Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
            ("LastWritten", _FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", POINTER(c_byte)),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", c_void_p),
            ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]


class WindowsCredentialManagerStore:
    """Store WITSML passwords in Windows Credential Manager.

    Only the stable credential identifier and user name are stored in application
    settings. The password never enters the project file or profile JSON.
    """

    _PREFIX = "GEOLOG_GASRATIO_Pixler/WITSML1411/"
    _CRED_TYPE_GENERIC = 1
    _CRED_PERSIST_LOCAL_MACHINE = 2
    _ERROR_NOT_FOUND = 1168

    def __init__(self) -> None:
        if os.name != "nt":
            raise WitsmlCredentialStoreError(
                "Windows Credential Manager is available only on Windows"
            )
        self._advapi32 = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        self._advapi32.CredWriteW.argtypes = [POINTER(_CREDENTIALW), wintypes.DWORD]
        self._advapi32.CredWriteW.restype = wintypes.BOOL
        self._advapi32.CredReadW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            POINTER(POINTER(_CREDENTIALW)),
        ]
        self._advapi32.CredReadW.restype = wintypes.BOOL
        self._advapi32.CredDeleteW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
        ]
        self._advapi32.CredDeleteW.restype = wintypes.BOOL
        self._advapi32.CredFree.argtypes = [c_void_p]
        self._advapi32.CredFree.restype = None

    def _target(self, credential_id: str) -> str:
        token = credential_id.strip()
        if not token or any(char in token for char in "\r\n\x00"):
            raise ValueError("credential_id must be a safe non-empty token")
        return f"{self._PREFIX}{token}"

    def save(self, credential_id: str, credentials: Witsml1411Credentials) -> None:
        target = self._target(credential_id)
        blob = credentials.password.encode("utf-16-le")
        blob_buffer = (c_byte * max(len(blob), 1))()
        if blob:
            ctypes.memmove(blob_buffer, blob, len(blob))
        credential = _CREDENTIALW()
        credential.Type = self._CRED_TYPE_GENERIC
        credential.TargetName = target
        credential.CredentialBlobSize = len(blob)
        credential.CredentialBlob = cast(blob_buffer, POINTER(c_byte))
        credential.Persist = self._CRED_PERSIST_LOCAL_MACHINE
        credential.UserName = credentials.username
        if not self._advapi32.CredWriteW(byref(credential), 0):
            error = ctypes.get_last_error()
            raise WitsmlCredentialStoreError(f"CredWriteW failed with error {error}")

    def load(self, credential_id: str) -> Witsml1411Credentials | None:
        target = self._target(credential_id)
        pointer = POINTER(_CREDENTIALW)()
        if not self._advapi32.CredReadW(
            target,
            self._CRED_TYPE_GENERIC,
            0,
            byref(pointer),
        ):
            error = ctypes.get_last_error()
            if error == self._ERROR_NOT_FOUND:
                return None
            raise WitsmlCredentialStoreError(f"CredReadW failed with error {error}")
        try:
            item = pointer.contents
            raw = (
                string_at(item.CredentialBlob, item.CredentialBlobSize)
                if item.CredentialBlobSize
                else b""
            )
            return Witsml1411Credentials(
                username=item.UserName or "",
                password=raw.decode("utf-16-le") if raw else "",
            )
        finally:
            self._advapi32.CredFree(pointer)

    def delete(self, credential_id: str) -> None:
        target = self._target(credential_id)
        if self._advapi32.CredDeleteW(target, self._CRED_TYPE_GENERIC, 0):
            return
        error = ctypes.get_last_error()
        if error != self._ERROR_NOT_FOUND:
            raise WitsmlCredentialStoreError(f"CredDeleteW failed with error {error}")


def default_witsml_credential_store() -> WitsmlCredentialStore:
    if os.name == "nt":
        return WindowsCredentialManagerStore()
    # Deliberately non-persistent outside Windows. This keeps passwords out of files
    # and allows Linux test/development environments to exercise the client safely.
    return InMemoryWitsmlCredentialStore()
