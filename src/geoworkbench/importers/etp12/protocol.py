from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import time
from typing import Awaitable, Callable, Protocol, Sequence

from geoworkbench.importers.etp12.models import (
    Etp12AuditEvent,
    Etp12ConnectionProfile,
    Etp12Credentials,
    Etp12MessageHeader,
    Etp12ReceivedMessage,
    Etp12SessionState,
)


class Etp12ProtocolError(RuntimeError):
    pass


class Etp12ConnectionClosed(Etp12ProtocolError):
    pass


class Etp12RequestTimeout(Etp12ProtocolError):
    pass


class Etp12MultipartLimitError(Etp12ProtocolError):
    pass


class Etp12MultipartTimeout(Etp12ProtocolError):
    pass


class Etp12RemoteError(Etp12ProtocolError):
    def __init__(self, message: str, *, body: object | None = None) -> None:
        self.body = body
        super().__init__(message)


class Etp12WireAdapter(Protocol):
    async def connect(
        self,
        profile: Etp12ConnectionProfile,
        credentials: Etp12Credentials,
    ) -> None: ...

    async def send(
        self,
        body: object,
        *,
        message_id: int,
        correlation_id: int,
        message_flags: int,
    ) -> None: ...

    async def recv(self) -> Etp12ReceivedMessage: ...
    async def close(self, reason: str) -> None: ...


class Etp12MessageFactory(Protocol):
    def request_session(self, profile: Etp12ConnectionProfile) -> object: ...
    def acknowledge(self) -> object: ...
    def close_session(self, reason: str) -> object: ...
    def is_open_session(self, body: object) -> bool: ...
    def is_acknowledge(self, body: object) -> bool: ...
    def is_protocol_exception(self, body: object) -> bool: ...
    def protocol_exception_message(self, body: object) -> str: ...


AuditCallback = Callable[[Etp12AuditEvent], None]
UnsolicitedHandler = Callable[[Etp12ReceivedMessage], Awaitable[None] | None]


@dataclass(slots=True)
class _PendingResponse:
    event: asyncio.Event
    messages: list[Etp12ReceivedMessage]
    error: BaseException | None = None
    encoded_size_bytes: int = 0
    multipart_started_at: float | None = None
    multipart_timeout_task: asyncio.Task[None] | None = None


class Etp12ProtocolEngine:
    """Correlation, multipart, acknowledgement and request timeout boundary.

    The engine is intentionally independent from Qt and from a concrete Avro
    implementation.  A production adapter encodes generated ETP v1.2 models;
    tests use an in-memory adapter but exercise the same state machine.
    """

    def __init__(
        self,
        adapter: Etp12WireAdapter,
        factory: Etp12MessageFactory,
        *,
        audit: AuditCallback | None = None,
    ) -> None:
        self.adapter = adapter
        self.factory = factory
        self.audit = audit
        self.profile: Etp12ConnectionProfile | None = None
        self.credentials = Etp12Credentials()
        self.state = Etp12SessionState.DISCONNECTED
        self._next_message_id = 2
        self._pending: dict[int, _PendingResponse] = {}
        self._receiver_task: asyncio.Task[None] | None = None
        self._unsolicited_handlers: list[UnsolicitedHandler] = []
        self.sent_messages = 0
        self.received_messages = 0
        self.acknowledgements_sent = 0
        self.acknowledgements_received = 0
        self.last_error: str | None = None
        self._send_lock = asyncio.Lock()

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    def add_unsolicited_handler(self, handler: UnsolicitedHandler) -> None:
        if handler not in self._unsolicited_handlers:
            self._unsolicited_handlers.append(handler)

    def remove_unsolicited_handler(self, handler: UnsolicitedHandler) -> None:
        if handler in self._unsolicited_handlers:
            self._unsolicited_handlers.remove(handler)

    async def connect(
        self,
        profile: Etp12ConnectionProfile,
        credentials: Etp12Credentials,
    ) -> Sequence[Etp12ReceivedMessage]:
        if self.state not in {Etp12SessionState.DISCONNECTED, Etp12SessionState.CLOSED, Etp12SessionState.FAILED}:
            raise Etp12ProtocolError(f"Cannot connect while state is {self.state.value}")
        self.profile = profile
        self.credentials = credentials
        self.state = Etp12SessionState.CONNECTING
        self.last_error = None
        started = time.monotonic()
        self._audit("connect", "started", attempt=1)
        try:
            await self.adapter.connect(profile, credentials)
            self._receiver_task = asyncio.create_task(self._receiver_loop(), name="etp12-receiver")
            self.state = Etp12SessionState.NEGOTIATING
            messages = await self.request(
                self.factory.request_session(profile),
                timeout=profile.request_timeout_seconds,
                request_ack=False,
            )
            if len(messages) != 1 or not self.factory.is_open_session(messages[0].body):
                raise Etp12ProtocolError("Server did not return exactly one OpenSession")
            self.state = Etp12SessionState.OPEN
            self._audit(
                "connect",
                "success",
                duration=time.monotonic() - started,
                metadata={"subprotocol": "etp12.energistics.org"},
            )
            return messages
        except Exception as exc:
            self.last_error = str(exc)
            self.state = Etp12SessionState.FAILED
            self._audit("connect", "failed", duration=time.monotonic() - started, detail=str(exc))
            await self._abort_pending(exc)
            try:
                await self.adapter.close("connection negotiation failed")
            except Exception:
                pass
            raise

    async def request(
        self,
        body: object,
        *,
        timeout: float | None = None,
        request_ack: bool | None = None,
    ) -> tuple[Etp12ReceivedMessage, ...]:
        if self.profile is None:
            raise Etp12ProtocolError("ETP profile is not configured")
        if self.state not in {Etp12SessionState.NEGOTIATING, Etp12SessionState.OPEN}:
            raise Etp12ProtocolError(f"Cannot send request while state is {self.state.value}")
        message_id = self._allocate_message_id()
        pending = _PendingResponse(asyncio.Event(), [])
        self._pending[message_id] = pending
        ack = self.profile.request_acknowledgement if request_ack is None else request_ack
        flags = Etp12MessageHeader.FIN | (Etp12MessageHeader.ACK_REQUESTED if ack else 0)
        started = time.monotonic()
        try:
            async with self._send_lock:
                await self.adapter.send(
                    body,
                    message_id=message_id,
                    correlation_id=0,
                    message_flags=flags,
                )
                self.sent_messages += 1
            self._audit(
                "send",
                "success",
                message_id=message_id,
                metadata={"body": body.__class__.__name__, "ack_requested": ack},
            )
            wait_timeout = timeout if timeout is not None else self.profile.request_timeout_seconds
            try:
                await asyncio.wait_for(pending.event.wait(), timeout=wait_timeout)
            except TimeoutError as exc:
                error = Etp12RequestTimeout(
                    f"ETP request {message_id} timed out after {wait_timeout:g} seconds"
                )
                if pending.multipart_started_at is not None:
                    pending.error = error
                    self._audit(
                        "multipart",
                        "failed",
                        correlation_id=message_id,
                        duration=time.monotonic() - pending.multipart_started_at,
                        detail=str(error),
                        metadata={
                            "parts": len(pending.messages),
                            "encoded_size_bytes": pending.encoded_size_bytes,
                        },
                    )
                    await self._fail_session(
                        error,
                        reason="ETP multipart request timeout",
                    )
                raise error from exc
            if pending.error is not None:
                raise pending.error
            self._audit(
                "response",
                "success",
                message_id=message_id,
                duration=time.monotonic() - started,
                metadata={
                    "parts": len(pending.messages),
                    "encoded_size_bytes": pending.encoded_size_bytes,
                },
            )
            return tuple(sorted(pending.messages, key=lambda item: item.header.message_id))
        except Exception as exc:
            self._audit(
                "response",
                "failed",
                message_id=message_id,
                duration=time.monotonic() - started,
                detail=str(exc),
            )
            raise
        finally:
            self._pending.pop(message_id, None)
            timeout_task = pending.multipart_timeout_task
            if timeout_task is not None and not timeout_task.done():
                timeout_task.cancel()

    async def send_unsolicited(
        self,
        body: object,
        *,
        correlation_id: int = 0,
        request_ack: bool = False,
    ) -> int:
        if self.state not in {Etp12SessionState.NEGOTIATING, Etp12SessionState.OPEN, Etp12SessionState.CLOSING}:
            raise Etp12ProtocolError(f"Cannot send while state is {self.state.value}")
        message_id = self._allocate_message_id()
        flags = Etp12MessageHeader.FIN | (Etp12MessageHeader.ACK_REQUESTED if request_ack else 0)
        async with self._send_lock:
            await self.adapter.send(
                body,
                message_id=message_id,
                correlation_id=correlation_id,
                message_flags=flags,
            )
            self.sent_messages += 1
        return message_id

    async def close(self, reason: str = "Client closing") -> None:
        if self.state in {Etp12SessionState.DISCONNECTED, Etp12SessionState.CLOSED}:
            return
        self.state = Etp12SessionState.CLOSING
        try:
            if self._receiver_task is not None and not self._receiver_task.done():
                try:
                    await self.send_unsolicited(self.factory.close_session(reason), request_ack=False)
                except Exception:
                    pass
            await self.adapter.close(reason)
        finally:
            task = self._receiver_task
            self._receiver_task = None
            if task is not None and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            await self._abort_pending(Etp12ConnectionClosed(reason))
            self.state = Etp12SessionState.CLOSED
            self._audit("close", "success", detail=reason)

    async def _receiver_loop(self) -> None:
        try:
            while True:
                message = await self.adapter.recv()
                self.received_messages += 1
                header = message.header
                self._audit(
                    "receive",
                    "success",
                    message_id=header.message_id,
                    correlation_id=header.correlation_id,
                    protocol=header.protocol,
                    message_type=header.message_type,
                    metadata={"body": message.body_name, "final": header.is_final},
                )
                if header.requests_acknowledgement and not self.factory.is_acknowledge(message.body):
                    await self._send_acknowledgement(header.message_id)
                if self.factory.is_acknowledge(message.body):
                    self.acknowledgements_received += 1
                    continue
                if self.factory.is_protocol_exception(message.body):
                    error = Etp12RemoteError(
                        self.factory.protocol_exception_message(message.body), body=message.body
                    )
                    if header.correlation_id in self._pending:
                        failed_pending = self._pending[header.correlation_id]
                        failed_pending.error = error
                        failed_pending.event.set()
                    else:
                        self.last_error = str(error)
                        await self._dispatch_unsolicited(message)
                    continue
                correlated_pending = self._pending.get(header.correlation_id)
                if correlated_pending is not None:
                    self._append_correlated_message(
                        header.correlation_id,
                        correlated_pending,
                        message,
                    )
                    if header.is_final:
                        correlated_pending.event.set()
                    continue
                await self._dispatch_unsolicited(message)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.last_error = str(exc)
            if self.state not in {Etp12SessionState.CLOSING, Etp12SessionState.CLOSED}:
                self.state = Etp12SessionState.FAILED
                self._audit("receiver", "failed", detail=str(exc))
            await self._fail_session(exc, reason="ETP receive loop failed")

    def _append_correlated_message(
        self,
        correlation_id: int,
        pending: _PendingResponse,
        message: Etp12ReceivedMessage,
    ) -> None:
        profile = self.profile
        if profile is None:
            raise Etp12ProtocolError("ETP profile is not configured")

        header = message.header
        multipart = bool(header.message_flags & Etp12MessageHeader.MULTIPART) or not header.is_final
        if pending.multipart_started_at is not None:
            multipart = True

        next_parts = len(pending.messages) + 1
        next_size = pending.encoded_size_bytes + message.encoded_size_bytes
        if multipart and next_parts > profile.max_multipart_parts:
            error = Etp12MultipartLimitError(
                f"ETP multipart response {correlation_id} exceeded the part limit of "
                f"{profile.max_multipart_parts}"
            )
            pending.error = error
            self._audit(
                "multipart",
                "failed",
                correlation_id=correlation_id,
                detail=str(error),
                metadata={
                    "parts": next_parts,
                    "encoded_size_bytes": next_size,
                    "limit": "parts",
                },
            )
            raise error
        if multipart and next_size > profile.max_multipart_bytes:
            error = Etp12MultipartLimitError(
                f"ETP multipart response {correlation_id} exceeded the encoded-size limit of "
                f"{profile.max_multipart_bytes} bytes"
            )
            pending.error = error
            self._audit(
                "multipart",
                "failed",
                correlation_id=correlation_id,
                detail=str(error),
                metadata={
                    "parts": next_parts,
                    "encoded_size_bytes": next_size,
                    "limit": "encoded_size_bytes",
                },
            )
            raise error

        pending.messages.append(message)
        pending.encoded_size_bytes = next_size
        if multipart and not header.is_final and pending.multipart_started_at is None:
            pending.multipart_started_at = time.monotonic()
            pending.multipart_timeout_task = asyncio.create_task(
                self._expire_multipart_response(correlation_id, pending),
                name=f"etp12-multipart-{correlation_id}",
            )

    async def _expire_multipart_response(
        self,
        correlation_id: int,
        pending: _PendingResponse,
    ) -> None:
        profile = self.profile
        if profile is None:
            return
        try:
            await asyncio.sleep(profile.multipart_timeout_seconds)
        except asyncio.CancelledError:
            raise
        if self._pending.get(correlation_id) is not pending or pending.event.is_set():
            return

        error = Etp12MultipartTimeout(
            f"ETP multipart response {correlation_id} did not finish within "
            f"{profile.multipart_timeout_seconds:g} seconds"
        )
        pending.error = error
        self._audit(
            "multipart",
            "failed",
            correlation_id=correlation_id,
            duration=profile.multipart_timeout_seconds,
            detail=str(error),
            metadata={
                "parts": len(pending.messages),
                "encoded_size_bytes": pending.encoded_size_bytes,
            },
        )
        await self._fail_session(error, reason="ETP multipart assembly timeout")

    async def _fail_session(self, error: BaseException, *, reason: str) -> None:
        self.last_error = str(error)
        if self.state not in {Etp12SessionState.CLOSING, Etp12SessionState.CLOSED}:
            self.state = Etp12SessionState.FAILED
        try:
            await self.adapter.close(reason)
        except Exception:
            pass
        receiver_task = self._receiver_task
        if (
            receiver_task is not None
            and receiver_task is not asyncio.current_task()
            and not receiver_task.done()
        ):
            receiver_task.cancel()
            try:
                await receiver_task
            except asyncio.CancelledError:
                pass
        await self._abort_pending(Etp12ConnectionClosed(str(error)))

    async def _send_acknowledgement(self, correlation_id: int) -> None:
        message_id = self._allocate_message_id()
        async with self._send_lock:
            await self.adapter.send(
                self.factory.acknowledge(),
                message_id=message_id,
                correlation_id=correlation_id,
                message_flags=Etp12MessageHeader.FIN,
            )
            self.sent_messages += 1
            self.acknowledgements_sent += 1
        self._audit(
            "acknowledge",
            "success",
            message_id=message_id,
            correlation_id=correlation_id,
        )

    async def _dispatch_unsolicited(self, message: Etp12ReceivedMessage) -> None:
        for handler in tuple(self._unsolicited_handlers):
            result = handler(message)
            if result is not None:
                await result

    async def _abort_pending(self, error: BaseException) -> None:
        for pending in tuple(self._pending.values()):
            if pending.error is None:
                pending.error = error
            pending.event.set()

    def _allocate_message_id(self) -> int:
        value = self._next_message_id
        self._next_message_id += 2
        if self._next_message_id > 2**63 - 2:
            self._next_message_id = 2
        return value

    def _audit(
        self,
        event: str,
        outcome: str,
        *,
        attempt: int = 1,
        message_id: int | None = None,
        correlation_id: int | None = None,
        protocol: int | None = None,
        message_type: int | None = None,
        duration: float | None = None,
        detail: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        if self.audit is None or self.profile is None:
            return
        self.audit(
            Etp12AuditEvent(
                timestamp_utc=datetime.now(timezone.utc),
                event=event,
                endpoint=self.profile.endpoint,
                outcome=outcome,
                state=self.state,
                attempt=attempt,
                message_id=message_id,
                correlation_id=correlation_id,
                protocol=protocol,
                message_type=message_type,
                duration_seconds=duration,
                detail=detail,
                metadata=metadata or {},
            )
        )
