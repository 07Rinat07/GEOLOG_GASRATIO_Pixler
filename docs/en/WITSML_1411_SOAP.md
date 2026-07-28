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
- a remote endpoint is allowed only over `https://` with certificate-chain and hostname
  verification;
- `http://` or disabled TLS verification is allowed only for loopback
  (`127.0.0.1`/`localhost`) in a controlled test;
- HTTP redirects are not followed: enter and independently confirm the final URL so credentials
  cannot be moved to another origin or a downgrade.

On a certificate error, stop and contact the server administrator. Never put the password in the
URL or disable verification for a remote address.

## Retry policy

Only transient transport failures and selected HTTP status codes are retried. SOAP faults and
negative WITSML result codes are not retried. Every attempt receives one audit record.

## Import path

The returned comma-separated LogData rows are parsed with CSV quoting support. The index curve is
selected from `indexCurve` or the first mnemonic. Null markers from `logCurveInfo/nullValue` are
converted to null values. The remote log is adapted to `WitsmlChannelSetData` and passed through the
existing Import Review and atomic project registration.
