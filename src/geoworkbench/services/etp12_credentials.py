from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Protocol

from geoworkbench.importers.etp12.models import Etp12Credentials
from geoworkbench.importers.witsml1411.models import Witsml1411Credentials
from geoworkbench.services.witsml_credentials import (
    InMemoryWitsmlCredentialStore,
    WindowsCredentialManagerStore,
    WitsmlCredentialStore,
)


class Etp12CredentialStore(Protocol):
    def load(self, credential_id: str) -> Etp12Credentials | None: ...
    def save(self, credential_id: str, credentials: Etp12Credentials) -> None: ...
    def delete(self, credential_id: str) -> None: ...


class WindowsEtp12CredentialStore(WindowsCredentialManagerStore):
    """Dedicated Credential Manager namespace for ETP 1.2 secrets."""

    _PREFIX = "GEOLOG_GASRATIO_Pixler/ETP12/"


@dataclass(slots=True)
class WitsmlCredentialStoreAdapter:
    """Adapt the generic secret backend without sharing credential namespaces."""

    delegate: WitsmlCredentialStore

    def load(self, credential_id: str) -> Etp12Credentials | None:
        value = self.delegate.load(credential_id)
        if value is None:
            return None
        return Etp12Credentials(username=value.username, secret=value.password)

    def save(self, credential_id: str, credentials: Etp12Credentials) -> None:
        self.delegate.save(
            credential_id,
            Witsml1411Credentials(credentials.username, credentials.secret),
        )

    def delete(self, credential_id: str) -> None:
        self.delegate.delete(credential_id)


def default_etp12_credential_store() -> Etp12CredentialStore:
    if os.name == "nt":
        return WitsmlCredentialStoreAdapter(WindowsEtp12CredentialStore())
    # Deliberately non-persistent on non-Windows systems. Profiles may be stored,
    # but bearer tokens and passwords disappear with the process.
    return WitsmlCredentialStoreAdapter(InMemoryWitsmlCredentialStore())
