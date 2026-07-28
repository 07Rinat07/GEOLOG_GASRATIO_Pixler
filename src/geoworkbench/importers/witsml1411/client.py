from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, TypedDict, Unpack

from geoworkbench.importers.witsml import WitsmlChannelSetData, WitsmlDataPackage
from geoworkbench.importers.witsml1411.models import (
    Witsml1411Capabilities,
    Witsml1411LogHeader,
    Witsml1411Well,
    Witsml1411Wellbore,
)
from geoworkbench.importers.witsml1411.parser import (
    log_data_to_channel_set,
    parse_capabilities,
    parse_log_data,
    parse_logs,
    parse_wellbores,
    parse_wells,
)
from geoworkbench.importers.witsml1411.queries import (
    log_data_query,
    logs_query,
    wellbores_query,
    wells_query,
)
from geoworkbench.importers.witsml1411.soap import Witsml1411SoapClient
from geoworkbench.services.witsml1411_audit import sanitize_endpoint


@dataclass(frozen=True, slots=True)
class Witsml1411Handshake:
    versions: tuple[str, ...]
    selected_version: str
    capabilities: Witsml1411Capabilities
    result_code: int
    supplementary_message: str | None


class Witsml1411LogFetchOptions(TypedDict, total=False):
    mnemonics: Iterable[str]
    start_index: str | None
    end_index: str | None
    start_datetime_index: str | None
    end_datetime_index: str | None
    max_data_nodes: int


class Witsml1411ReadOnlyService:
    """Hierarchy and log-data facade over the low-level SOAP client."""

    def __init__(self, soap: Witsml1411SoapClient) -> None:
        self.soap = soap
        self._handshake: Witsml1411Handshake | None = None

    @property
    def handshake_state(self) -> Witsml1411Handshake | None:
        return self._handshake

    def handshake(self) -> Witsml1411Handshake:
        versions = self.soap.get_version()
        requested = self.soap.profile.data_version
        selected = requested if requested in versions else _select_1411_version(versions)
        if selected is None:
            raise ValueError(
                f"Server does not advertise WITSML 1.4.1.x support: {', '.join(versions)}"
            )
        result, raw_capabilities, supplementary = self.soap.get_capabilities(selected)
        capabilities = parse_capabilities(raw_capabilities, selected)
        state = Witsml1411Handshake(
            versions=versions,
            selected_version=selected,
            capabilities=capabilities,
            result_code=result,
            supplementary_message=supplementary,
        )
        self._handshake = state
        return state

    def list_wells(self) -> tuple[Witsml1411Well, ...]:
        self._ensure_ready()
        _result, xml_out, _supp = self.soap.get_from_store(
            "well",
            wells_query(),
            options_in="returnElements=requested",
        )
        return parse_wells(xml_out)

    def list_wellbores(self, uid_well: str) -> tuple[Witsml1411Wellbore, ...]:
        self._ensure_ready()
        _result, xml_out, _supp = self.soap.get_from_store(
            "wellbore",
            wellbores_query(uid_well),
            options_in="returnElements=requested",
            selection={"uidWell": uid_well},
        )
        return parse_wellbores(xml_out)

    def list_logs(self, uid_well: str, uid_wellbore: str) -> tuple[Witsml1411LogHeader, ...]:
        self._ensure_ready()
        _result, xml_out, _supp = self.soap.get_from_store(
            "log",
            logs_query(uid_well, uid_wellbore),
            options_in="returnElements=requested",
            selection={"uidWell": uid_well, "uidWellbore": uid_wellbore},
        )
        return parse_logs(xml_out)

    def fetch_log_channel_set(
        self,
        log: Witsml1411LogHeader,
        *,
        mnemonics: Iterable[str] = (),
        start_index: str | None = None,
        end_index: str | None = None,
        start_datetime_index: str | None = None,
        end_datetime_index: str | None = None,
        max_data_nodes: int = 200_000,
    ) -> WitsmlChannelSetData:
        if isinstance(mnemonics, (str, bytes)):
            raise TypeError("mnemonics must be an iterable of strings, not str or bytes")
        selected_mnemonics = tuple(mnemonics)
        if not all(isinstance(item, str) for item in selected_mnemonics):
            raise TypeError("mnemonics must contain only strings")
        if (
            isinstance(max_data_nodes, bool)
            or not isinstance(max_data_nodes, int)
            or max_data_nodes < 1
        ):
            raise ValueError("max_data_nodes must be a positive integer")
        self._ensure_ready()
        query = log_data_query(
            log.uid_well,
            log.uid_wellbore,
            log.uid,
            mnemonics=selected_mnemonics,
            start_index=start_index,
            end_index=end_index,
            start_datetime_index=start_datetime_index,
            end_datetime_index=end_datetime_index,
        )
        _result, xml_out, _supp = self.soap.get_from_store(
            "log",
            query,
            options_in=f"returnElements=requested;maxDataNodes={max_data_nodes}",
            selection={
                "uidWell": log.uid_well,
                "uidWellbore": log.uid_wellbore,
                "uidLog": log.uid,
            },
        )
        parsed = parse_log_data(xml_out)
        return log_data_to_channel_set(
            parsed,
            endpoint_label=sanitize_endpoint(self.soap.profile.endpoint),
        )

    def fetch_log_package(
        self,
        log: Witsml1411LogHeader,
        **kwargs: Unpack[Witsml1411LogFetchOptions],
    ) -> WitsmlDataPackage:
        channel_set = self.fetch_log_channel_set(log, **kwargs)
        return WitsmlDataPackage(
            source=channel_set.source,
            channel_sets=(channel_set,),
            issues=channel_set.issues,
        )

    def _ensure_ready(self) -> Witsml1411Handshake:
        return self._handshake or self.handshake()


def _select_1411_version(versions: tuple[str, ...]) -> str | None:
    candidates = [item for item in versions if item.startswith("1.4.1")]
    return sorted(candidates, reverse=True)[0] if candidates else None
