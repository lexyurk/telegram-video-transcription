# Zoom Integration — TODO

## Setup
- [ ] Create Zoom user-managed OAuth app; enable `recording.completed` (and optional `recording.transcript_completed`).
- [ ] Configure Deauthorization Notification URL.
- [x] Add env vars: `ZOOM_CLIENT_ID`, `ZOOM_CLIENT_SECRET`, `ZOOM_REDIRECT`, `ZOOM_WEBHOOK_SECRET`, `STATE_SECRET`, `TELEGRAM_BOT_TOKEN` (wired in code; fill values in `.env`).
- [ ] Add redirect URI in Zoom app: `https://api.yourapp.com/zoom/callback`.

## Backend endpoints
- [x] `GET /zoom/connect` returns Zoom authorize URL (JWT `state` with `chat_id`, `telegram_user_id`).
- [x] `GET /zoom/callback` exchanges code→tokens, fetches `users/me`, stores mapping and tokens.
- [x] `POST /webhooks/zoom` handles CRC (`endpoint.url_validation`) and verifies `x-zm-signature` on every request.
- [x] `POST /webhooks/zoom/deauth` cleans up tokens on uninstall.

## Token & DB
- [x] Define tables: `users`, `zoom_connections`, `meetings`, `recordings`, `jobs`.
- [x] Add unique index on `zoom_connections.zoom_user_id`.
- [x] Implement token refresh.
- [ ] Encrypt tokens at rest.

## Recording processing worker
- [x] Queue job on `recording.completed` with `(meeting_uuid, zoom_user_id, chat_id)` (FastAPI background task).
- [x] Fetch recordings via `GET /v2/meetings/{double-encoded uuid}/recordings?include_fields=download_access_token&ttl=60`.
- [x] Prefer `recording_type == "audio_only"`; fallback otherwise.
- [x] Download via `download_url` using `download_access_token` or OAuth bearer.
- [ ] Idempotency: skip already-processed `(meeting_uuid, file_id)`.
- [ ] Send to Telegram using `sendAudio` (≤2 GB); fallback to `sendDocument` if needed.

## Telegram bot
- [x] Add `/connect` command that deep-links to `GET /zoom/connect?telegram_chat_id=...&telegram_user_id=...`.
- [x] Add `/status` to show connected Zoom backend reachability.
- [x] Add `/disconnect` to revoke and purge tokens (via Zoom uninstall flow).

## Security & Reliability
- [x] Strict signature verification and timestamp tolerance.
- [x] CRC response within 3 seconds.
- [ ] Retries with exponential backoff on Zoom 429/5xx and transient download failures.
- [ ] Size guardrails; storage TTL for temporary media files.
- [ ] Structured logging, metrics, and alerts.

## Optional Enhancements
- [ ] Use `recording.transcript_completed` to pull Zoom transcript if available.
- [x] Include topic and start time in caption; summary delivered as a message.
- [ ] Include short summary directly in caption (optional).
- [ ] Multi-language support based on `users.locale`.


