# GEOLOG GASRATIO@Pixler 0.7.80 — WITSML 1.4.1.1 SOAP read-only

## Read-only Store API client

Added a strict SOAP 1.1 client for the legacy WITSML Store API operations `WMLS_GetVersion`,
`WMLS_GetCap` and `WMLS_GetFromStore`. The client deliberately rejects mutating operations and
supports Well → Wellbore → Log → LogCurveInfo → LogData navigation.

## Network reliability and audit

Each call has a configurable timeout, bounded exponential retry for transient transport/HTTP
failures, response-size limits, DTD/entity rejection and an append-only hash-chained JSONL audit.
The audit stores operation metadata and result codes, but never request XML, passwords or
Authorization headers.

## Credentials outside the project

Connection profiles contain only endpoint, username, credential identifier and public connection
settings. On Windows, passwords are stored in Windows Credential Manager. Non-Windows development
uses a non-persistent in-memory credential store. No credential is written to a project Dataset or
project file.

## Log import reuse

Retrieved WITSML 1.4.1.1 LogData is converted to the existing immutable ChannelSet import model.
The same Semantic Channel Dictionary, UOM conversion, Import Review, Dataset digest and atomic
project-registration boundary used by the WITSML 2.x offline importer are reused.

The parallel real-GSWITS Windows reliability gate remains open. Project format remains v20, form
schema v8 and tablet layout v18.
