# WebSocket Protocol

This page documents TradingView's custom WebSocket protocol as implemented by tvkit. It is intended for contributors and advanced users who need to understand the message flow.

## Endpoint

```text
wss://data.tradingview.com/socket.io/websocket
```

The connection uses standard WebSocket (WSS). No subprotocol negotiation is required.

> **Note**: TradingView may append query parameters (e.g. `?from=chart&date=...`) when the client is the web browser. These are not strictly required for the protocol to function.

## Message Framing

TradingView does not use raw JSON or a standard sub-protocol. Every message is wrapped in a custom frame:

```text
~m~<length>~m~<payload>
```

Where:

- `~m~` is a literal delimiter
- `<length>` is the byte length of `<payload>` as a decimal integer
- `<payload>` is the JSON body

Example:

```text
~m~52~m~{"m":"set_auth_token","p":["unauthorized_user_token"]}
```

A single WebSocket message may contain multiple frames concatenated together:

```text
~m~52~m~{"m":"set_auth_token","p":["unauthorized_user_token"]}~m~34~m~{"m":"chart_create_session","p":[...]}
```

tvkit's `MessageService` handles frame construction and parsing automatically.

## Session Initialization Sequence

Every connection follows this sequence before data can be requested:

```text
Client                              TradingView
  │                                      │
  │──── WebSocket connect ──────────────▶│
  │                                      │
  │◀─── server hello (~m~N~m~...) ───────│
  │                                      │
  │──── set_auth_token ─────────────────▶│
  │──── chart_create_session ───────────▶│
  │──── quote_create_session ───────────▶│
  │──── quote_set_fields ───────────────▶│
  │──── quote_add_symbols ──────────────▶│
  │──── resolve_symbol ─────────────────▶│
  │──── create_series ──────────────────▶│
  │                                      │
  │◀─── series_loading ─────────────────│
  │◀─── symbol_resolved ────────────────│
  │◀─── series data (du) ───────────────│
  │◀─── series_completed ───────────────│
  │◀─── heartbeats (~m~N~m~~h~N) ───────│
```

## Connection Lifecycle and State Machine

The client follows an explicit connection state machine. Each state maps to a distinct phase of the WebSocket session:

```text
         ┌─────────────────────────────────┐
         │                                 │
    ┌────▼────┐                      ┌─────┴──────┐
    │  IDLE   │──── connect() ──────▶│ CONNECTING │
    └─────────┘                      └─────┬──────┘
                                           │ success
                                    ┌──────▼──────┐
                                    │  STREAMING  │◀─────┐
                                    └──────┬──────┘      │
                                           │ unexpected   │
                                           │ close        │
                                    ┌──────▼──────┐      │
                                    │RECONNECTING │      │
                                    └──────┬──────┘      │
                                           │ success ─────┘
                                           │ exhausted
                                    ┌──────▼──────┐
                                    │   FAILED    │
                                    └─────────────┘
```

| From | Event | To | Action |
| --- | --- | --- | --- |
| `IDLE` | `connect()` called | `CONNECTING` | Open WebSocket |
| `CONNECTING` | Connection success | `STREAMING` | Start reader task |
| `STREAMING` | Unexpected close (`1006`) | `RECONNECTING` | Start backoff loop |
| `STREAMING` | Clean close (`1000`) | `IDLE` | No retry |
| `STREAMING` | `close()` called | `IDLE` | Set `_closing`, skip retry |
| `RECONNECTING` | Attempt success | `STREAMING` | Invoke `on_reconnect`, resume stream |
| `RECONNECTING` | Attempts exhausted | `FAILED` | Raise `StreamConnectionError` |

### Reconnect Path

When an unexpected close is detected, the client enters a backoff retry loop before re-establishing the connection:

```text
STREAMING
    │ unexpected close (code 1006)
    ▼
RECONNECTING
    │
    ├── _reset_connection()        ← cancel reader task, free WS reference
    │
    ├── calculate_backoff_delay()  ← min(base × 2^(attempt-1), max_backoff)
    │
    ├── asyncio.sleep(delay)
    │
    ├── reconnect WebSocket
    │       │ success
    │       ▼
    │   STREAMING ─── on_reconnect() ─── restore subscription
    │       │ failure
    │       ▼
    │   next attempt …
    │
    └── attempts exhausted → FAILED → StreamConnectionError
```

**Intentional close path**: calling `close()` sets a `_closing` flag before tearing down the connection. The retry logic checks this flag on entry and skips the backoff loop entirely, so the stream ends cleanly without retrying.

**Single loop guarantee**: if two callers observe the same connection failure simultaneously, only the first enters the retry loop. The second returns immediately because the state is already `RECONNECTING`.

See [Connection Service Internals](../internals/connection-service.md#retry-strategy) for implementation details and configurable parameters.

---

## Full Example Message Flow

A minimal session for fetching 5 daily bars of `NASDAQ:AAPL`:

```text
Client → set_auth_token          (authenticate)
Client → chart_create_session    (open chart session cs_abc123)
Client → quote_create_session    (open quote session qs_def456)
Client → quote_set_fields        (specify which quote fields to return)
Client → quote_add_symbols       (subscribe to NASDAQ:AAPL quote)
Client → resolve_symbol          (resolve NASDAQ:AAPL for the chart session)
Client → create_series           (request 5 daily bars)

Server → symbol_resolved         (symbol metadata confirmed)
Server → series_loading          (bars are being loaded)
Server → du                      (bar data — may arrive in multiple du messages)
Server → series_completed        (all requested bars delivered)
```

## Key Protocol Messages

### Authentication

```json
{"m": "set_auth_token", "p": ["unauthorized_user_token"]}
```

tvkit uses `"unauthorized_user_token"`, which grants access equivalent to an anonymous TradingView browser session. Authenticated sessions require a valid user token.

### Session Creation

```json
{"m": "chart_create_session", "p": ["cs_<random_12_chars>", ""]}
{"m": "quote_create_session", "p": ["qs_<random_12_chars>"]}
```

Session identifiers use a fixed prefix followed by a random 12-character string:

- `cs_` prefix for chart sessions
- `qs_` prefix for quote sessions

tvkit generates these using `MessageService.generate_session(prefix)`, which produces a cryptographically random suffix. Sessions are scoped to the WebSocket connection lifetime.

### Symbol Resolution

```json
{"m": "resolve_symbol", "p": ["cs_<session>", "sds_sym_1", "={\"symbol\":\"NASDAQ:AAPL\",\"adjustment\":\"splits\"}"]}
```

The symbol descriptor is a JSON object encoded as a **string inside the parameter array** — it is JSON-encoded twice. The outer array element is a JSON string; the value of that string is itself a JSON object. This is a frequent source of confusion when manually implementing the protocol.

### Series Creation — Count Mode

```json
{"m": "create_series", "p": ["cs_<session>", "sds_1", "s1", "sds_sym_1", "1D", 300]}
```

Parameters in order: chart session ID, series ID, series key, symbol alias, interval, bar count.

### Series Creation — Date Range Mode

```json
{"m": "create_series", "p": ["cs_<session>", "sds_1", "s1", "sds_sym_1", "1D", 0, "r,<start_unix>:<end_unix>"]}
```

The 6th parameter is `0` (bar count, unused in range mode). The 7th parameter is the range string: `r,<start_unix_seconds>:<end_unix_seconds>`.

### Modifying a Series

```json
{"m": "modify_series", "p": ["cs_<session>", "sds_1", "s1", "sds_sym_1", "1D", 300]}
```

Used to change bar count or date range after the initial series, without re-creating the session.

## Server Response Format

### Series Loading Lifecycle

```json
{"m": "series_loading", "p": ["cs_<session>", "sds_1"]}
```

Sent when bars have started loading. One or more `du` messages follow.

```json
{"m": "series_completed", "p": ["cs_<session>", "sds_1"]}
```

Sent when all requested bars have been delivered. tvkit uses this message to know when to stop waiting for bar data.

### Bar Data (`du` — data update)

`du` stands for **data update**. The server may send multiple `du` messages as bars are loaded in batches.

```json
{
  "m": "du",
  "p": [
    "cs_<session>",
    {
      "sds_1": {
        "s": [
          {"i": 0, "v": [1720000000, 192.50, 193.00, 191.80, 192.75, 54320000]},
          {"i": 1, "v": [1720086400, 193.10, 194.20, 192.90, 193.85, 48750000]}
        ],
        "ns": {"d": "", "indexes": "s"},
        "t": "s"
      }
    }
  ]
}
```

Each bar in `s` is an object with:

- `i` — bar index
- `v` — array of `[timestamp, open, high, low, close, volume]`

## Heartbeat Handling

TradingView sends periodic heartbeat messages:

```text
~m~5~m~~h~42
```

The client must echo the exact payload back:

```text
Server → ~m~5~m~~h~42
Client → ~m~5~m~~h~42
```

If the client does not respond, the server drops the connection. tvkit's `ConnectionService` detects heartbeat messages and responds automatically.

## Error Responses

If a symbol cannot be resolved:

```json
{"m": "symbol_error", "p": ["cs_<session>", "sds_sym_1", "Unknown symbol"]}
```

tvkit's `ConnectionService` checks for this message and raises an exception before the data request is sent.

## See Also

- [Connection Service](../internals/connection-service.md) — implementation of session management
- [Message Service](../internals/message-service.md) — implementation of message construction and framing
- [System Overview](system-overview.md) — where these services fit in the overall architecture
