# WITSML 1.4.1.1 SOAP read-only integration

## Scope

The implementation exposes only `WMLS_GetVersion`, `WMLS_GetCap` and `WMLS_GetFromStore`. It does
not expose Add, Update or Delete operations. The hierarchy is discovered in this order:

`Well → Wellbore → Log → LogCurveInfo → LogData`.

## Security boundary

- endpoint URLs may not embed user information;
- passwords are not serialized with profiles or projects;
- Windows persistence uses Windows Credential Manager;
- SOAP DTD/entity declarations are rejected;
- response size is bounded;
- audit events contain no request XML or Authorization data;
- TLS certificate verification is enabled by default.

## Retry policy

Only transient transport failures and selected HTTP status codes are retried. SOAP faults and
negative WITSML result codes are not retried. Every attempt receives one audit record.

## Import path

The returned comma-separated LogData rows are parsed with CSV quoting support. The index curve is
selected from `indexCurve` or the first mnemonic. Null markers from `logCurveInfo/nullValue` are
converted to null values. The remote log is adapted to `WitsmlChannelSetData` and passed through the
existing Import Review and atomic project registration.
