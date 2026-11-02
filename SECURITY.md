# Security Policy

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Use GitHub's private security advisory system to report vulnerabilities
confidentially:

**[Open a private security advisory →](https://github.com/lumduan/tvkit/security/advisories/new)**

Include as much of the following information as possible to help us understand
and reproduce the issue:

- Type of vulnerability (e.g., injection, credential exposure, SSRF)
- File paths and line numbers relevant to the vulnerability
- Step-by-step reproduction instructions
- Proof-of-concept or exploit code (if available)
- Impact assessment — what an attacker could achieve

## Response Timeline

| Stage | Target time |
|-------|-------------|
| Acknowledgement | Within 48 hours |
| Initial assessment | Within 5 business days |
| Fix or mitigation plan | Within 14 days for critical issues |
| Public disclosure | Coordinated with reporter after fix is released |

We follow coordinated disclosure. We will work with you to agree on a public
disclosure date once a fix is available. We credit reporters in release notes
unless you prefer to remain anonymous.

## Supported Versions

Security fixes are applied to the latest release only. We do not backport fixes
to older versions.

| Version | Supported |
|---------|-----------|
| 0.18.x (latest) | Yes |
| < 0.18.0 | No |

We recommend always running the latest published version:

```bash
uv add tvkit        # or: pip install --upgrade tvkit
```

## Scope

This policy covers vulnerabilities in the tvkit library itself. It does not
cover:

- TradingView's own APIs or infrastructure
- Third-party dependencies (report those upstream)
- Issues in user code that uses tvkit incorrectly

## Security Design Notes

tvkit is a client library. Its primary security surface is:

- **Network requests** — all HTTP and WebSocket connections use TLS. The library
  does not disable certificate verification.
- **No credential storage** — tvkit stores no API keys or secrets. All
  configuration is supplied by the caller at runtime. The optional capability probe
  cache (`~/.cache/tvkit/capabilities.json`) holds a user ID, plan name and bar limit,
  never cookies or tokens; its directory is created `0700` and the file `0600`.
- **Session credentials stay on TradingView** — the TradingView session cookies are
  bound to `.tradingview.com`, and the authenticated profile request refuses any
  redirect hop that leaves `https://*.tradingview.com`. Browser cookies whose domain is
  not tradingview.com or a subdomain of it (look-alike hosts) are discarded on
  extraction.
- **Credentials are not logged** — the outgoing `set_auth_token` frame is logged with
  its parameters redacted, so DEBUG output is safe to share. Third-party loggers are
  outside tvkit's control: at DEBUG the `websockets` library logs each frame elided to
  its first 48 and last 24 characters — for `set_auth_token`, the token's first 10
  characters (its constant JWT header) and last ~20 (a fragment of the signature).
- **Exported cookies are owner-only** — `scripts/export_tv_cookies.py` (repository
  tool, not part of the package) writes the cookie file `0600`.
- **No user input passed to shell** — tvkit does not invoke shell commands or
  subprocess calls.
- **Async I/O only** — the library uses `httpx` and `websockets`; the
  synchronous `requests` and `websocket-client` libraries are not used.

If you identify a bypass of any of these properties, please report it.
