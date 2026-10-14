# Public connection lifecycle

States: CONNECTING, WAITING, LIVE, RECONNECTING, STALE, DISCONNECTED, ACCESS_DENIED, SESSION_ENDED, PROVIDER_UNAVAILABLE. Transport and presentation states are exposed separately.

1. Manual Start live validates the selected session's published start window and reuses a shared existing transport.
2. Public negotiation uses verified TLS, an explicit application user agent, bounded 5/15-second HTTP timeouts and no authenticated redirects. The SignalR library supplies its handshake/parser and 15-second keep-alive.
3. Subscribe once on each physical connection. SessionInfo must match key, meeting, name/type, season and UTC start (30-minute schedule tolerance) before accepting other topics.
4. Subscription snapshots without source UTC remain PARTIAL. LIVE requires matching identity and actual fresh dated TimingData. A healthy socket alone is WAITING. A change to another session marks prior observations stale and ignores its data.
5. Source age exceeding configured 20 seconds becomes STALE. Missing Position.z/CarData.z remain MISSING even when TimingData is LIVE. The physical connection is restarted after a 60-second observation silence or a close/error.
6. Exponential retry delay starts at one second, doubles up to 60 seconds, with 0–0.5-second jitter. At most six consecutive attempts in a ten-minute failure window; two minutes of observed stable live activity reset the failure budget. No recursive restart callbacks or second library reconnect loop exists.
7. HTTP 401/403 stops with ACCESS_DENIED. No token acquisition, browser cookie extraction, user-agent rotation or paywall workaround is attempted.
8. Explicit SessionInfo finalisation sets SESSION_ENDED. A qualifying segment finish remains an intermission; its next Started patch continues the same session. The session supervisor also enforces the existing six-hour / final-finish grace bound.
9. Explicit Stop live and process exit close transports. Closing the site's tab does not stop a popout's shared feed. The Stop button stops that shared session deliberately.

Checkpoints are atomic gzip files under `data/cache/race-control/observed`. Only bounded observations/current state/provenance are saved, not connection objects, headers, cookies or credentials. Recovery requires matching session/meeting/start/name, is always STALE, and never initiates a connection by itself. A newly verified fresh TimingData observation can clear recovery status; old field timestamps remain old. Eight session checkpoints and 30-day retention are enforced; malformed/oversized files are ignored.
