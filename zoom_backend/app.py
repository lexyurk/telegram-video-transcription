import base64
import asyncio
import hashlib
import hmac
import json
import os
import time
import urllib.parse
import re
from typing import Any, Dict, Optional, List

import httpx
import jwt
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from loguru import logger

from telegram_bot.config import get_settings
from telegram_bot.services.transcription_service import TranscriptionService
from telegram_bot.services.summarization_service import SummarizationService
from telegram_bot.services.speaker_identification_service import SpeakerIdentificationService
from telegram_bot.services.file_service import FileService
from zoom_backend.db import (
    ensure_db,
    get_conn,
    upsert_user,
    save_connection,
    get_chat_id_for_zoom_user,
    get_connection_by_zoom_user_id,
    delete_connection,
    upsert_meeting,
    insert_recording_if_new,
    update_tokens_by_zoom_user_id,
)


app = FastAPI(title="Zoom Integration Backend")


def _double_encode_uuid(uuid: str) -> str:
    return urllib.parse.quote(urllib.parse.quote(uuid, safe=""), safe="")


@app.on_event("startup")
async def startup_event() -> None:
    settings = get_settings()
    ensure_db(settings.zoom_db_path)


@app.get("/zoom/connect", response_model=None)
async def zoom_connect(telegram_chat_id: int, telegram_user_id: int, redirect: bool = False):
    settings = get_settings()
    if not (settings.zoom_client_id and settings.zoom_redirect and settings.state_secret):
        raise HTTPException(status_code=500, detail="Zoom not configured")

    state = jwt.encode(
        {"chat_id": telegram_chat_id, "uid": telegram_user_id, "ts": int(time.time())},
        settings.state_secret,
        algorithm="HS256",
    )
    params = {
        "response_type": "code",
        "client_id": settings.zoom_client_id,
        "redirect_uri": settings.zoom_redirect,
        "state": state,
    }
    url = f"https://zoom.us/oauth/authorize?{urllib.parse.urlencode(params)}"
    if redirect:
        return RedirectResponse(url=url, status_code=307)
    return {"authorize_url": url}


@app.get("/zoom/callback")
async def zoom_callback(code: str, state: str) -> PlainTextResponse:
    settings = get_settings()
    try:
        s = jwt.decode(state, settings.state_secret, algorithms=["HS256"])  # type: ignore[arg-type]
    except Exception:
        raise HTTPException(status_code=400, detail="bad state")

    basic = base64.b64encode(f"{settings.zoom_client_id}:{settings.zoom_client_secret}".encode()).decode()
    async with httpx.AsyncClient(timeout=20.0) as client:
        tok = await client.post(
            "https://zoom.us/oauth/token",
            headers={"Authorization": f"Basic {basic}"},
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": settings.zoom_redirect},
        )
        try:
            tok.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=400, detail=f"token exchange failed: {e.response.text}")
        tokens = tok.json()

        me = await client.get(
            "https://api.zoom.us/v2/users/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        me.raise_for_status()
        zoom_user = me.json()

    with get_conn(settings.zoom_db_path) as conn:
        user_id = upsert_user(conn, int(s["uid"]), int(s["chat_id"]))
        save_connection(conn, zoom_user["id"], user_id, tokens, email=zoom_user.get("email"))

    return PlainTextResponse("Zoom connected! You can close this window.")


def verify_signature(headers: Dict[str, str], raw_body: bytes, secret: str, tolerance_seconds: int = 300) -> bool:
    ts = headers.get("x-zm-request-timestamp")
    sig = headers.get("x-zm-signature")  # format: v0=hex
    if not ts or not sig:
        return False
    try:
        if abs(int(time.time()) - int(ts)) > tolerance_seconds:
            return False
    except Exception:
        return False
    msg = f"v0:{ts}:{raw_body.decode()}".encode()
    digest = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
    return sig == f"v0={digest}"


@app.post("/webhooks/zoom")
async def zoom_webhook(request: Request, background_tasks: BackgroundTasks):
    settings = get_settings()
    raw = await request.body()
    # Log key request details (no secrets)
    logger.info(
        "Zoom webhook POST: ua={}, ts={}, sig={}, content_length={}",
        request.headers.get("user-agent"),
        request.headers.get("x-zm-request-timestamp"),
        (request.headers.get("x-zm-signature") or "")[:16] + "...",
        request.headers.get("content-length"),
    )
    try:
        body = json.loads(raw.decode())
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")

    # CRC validation
    if body.get("event") == "endpoint.url_validation":
        plain = body["payload"]["plainToken"]
        enc_hex = hmac.new(
            settings.zoom_webhook_secret.encode(), plain.encode(), hashlib.sha256
        ).hexdigest()
        logger.info(
            "CRC handled (hex): plainToken_len={}, encryptedToken_prefix={}...",
            len(plain), enc_hex[:12]
        )
        return JSONResponse({"plainToken": plain, "encryptedToken": enc_hex})

    if not verify_signature(request.headers, raw, settings.zoom_webhook_secret):
        raise HTTPException(status_code=401, detail="bad signature")

    event = body.get("event")
    if event in ("recording.completed", "recording.transcript_completed"):
        obj = body["payload"]["object"]
        zoom_user_id = obj["host_id"]
        meeting_uuid = obj["uuid"]
        logger.info("{}: host_id={}, uuid_prefix={}...", event, zoom_user_id, str(meeting_uuid)[:10])

        # Look up chat_id
        with get_conn(settings.zoom_db_path) as conn:
            chat_id = get_chat_id_for_zoom_user(conn, zoom_user_id)
            # upsert meeting and recording rows for idempotency
            meeting_id = upsert_meeting(
                conn,
                meeting_uuid,
                obj.get("topic"),
                obj.get("start_time"),
                zoom_user_id,
            )
            # Mark new recordings; use file_id as unique key
            for f in obj.get("recording_files", []):
                file_id = f.get("id") or f.get("file_id") or f.get("download_url", "")
                insert_recording_if_new(
                    conn,
                    meeting_id,
                    file_id,
                    f.get("recording_type"),
                    f.get("download_url"),
                )
        if not chat_id:
            return JSONResponse({"ok": True})

        # Enqueue background processing to respond fast to Zoom
        background_tasks.add_task(
            process_recording,
            meeting_uuid,
            zoom_user_id,
            int(chat_id),
            obj.get("recording_files", []),
            obj.get("topic"),
            obj.get("start_time"),
        )
        return JSONResponse({"ok": True})

    return JSONResponse({"ok": True})


async def process_recording(
    meeting_uuid: str,
    zoom_user_id: str,
    chat_id: int,
    recording_files_from_event: Optional[list] = None,
    topic: Optional[str] = None,
    start_time: Optional[str] = None,
) -> None:
    settings = get_settings()
    # get fresh tokens (no refresh implemented yet)
    with get_conn(settings.zoom_db_path) as conn:
        conn_row = get_connection_by_zoom_user_id(conn, zoom_user_id)
        if not conn_row:
            return
        access_token = conn_row["access_token"]
        refresh_token = conn_row["refresh_token"]
        expires_at = int(conn_row["expires_at"]) if conn_row["expires_at"] is not None else 0

    # Refresh token if expired/near expiry
    if expires_at and expires_at - int(time.time()) < 30:
        basic = base64.b64encode(f"{settings.zoom_client_id}:{settings.zoom_client_secret}".encode()).decode()
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                "https://zoom.us/oauth/token",
                headers={"Authorization": f"Basic {basic}"},
                data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            )
            if resp.status_code == 200:
                new_tokens = resp.json()
                with get_conn(settings.zoom_db_path) as conn:
                    update_tokens_by_zoom_user_id(conn, zoom_user_id, new_tokens)
                access_token = new_tokens.get("access_token", access_token)

    async def fetch_recording_files(access_token: str, meeting_uuid: str) -> Dict[str, Any]:
        uid = _double_encode_uuid(meeting_uuid)
        url = f"https://api.zoom.us/v2/meetings/{uid}/recordings"
        params = {"include_fields": "download_access_token", "ttl": "60"}
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.get(url, headers={"Authorization": "Bearer " + access_token}, params=params)
            r.raise_for_status()
            return r.json()

    async def fetch_meeting_participants(access_token: str, meeting_uuid: str) -> list[str]:
        """
        Fetch participants for the meeting from Zoom to use their display names as speaker labels.
        We'll try two endpoints: participants (past meeting) and fallback to recording participants.
        Names are returned as a list preserving API order.
        """
        uid = _double_encode_uuid(meeting_uuid)
        names: list[str] = []
        async with httpx.AsyncClient(timeout=30.0) as c:
            # Try past meeting participants
            try:
                url1 = f"https://api.zoom.us/v2/past_meetings/{uid}/participants"
                r1 = await c.get(url1, headers={"Authorization": "Bearer " + access_token})
                if r1.status_code == 200:
                    js = r1.json()
                    for p in js.get("participants", []) or []:
                        nm = (p.get("name") or p.get("user_name") or "").strip()
                        if nm:
                            names.append(nm)
            except Exception:
                pass
            # Fallback to recording participants list
            if not names:
                try:
                    url2 = f"https://api.zoom.us/v2/meetings/{uid}/recordings"
                    r2 = await c.get(url2, headers={"Authorization": "Bearer " + access_token})
                    if r2.status_code == 200:
                        js2 = r2.json()
                        for p in js2.get("participants", []) or []:
                            nm = (p.get("name") or p.get("user_name") or "").strip()
                            if nm:
                                names.append(nm)
                except Exception:
                    pass
        # De-duplicate while preserving order
        seen = set()
        uniq = []
        for nm in names:
            if nm not in seen:
                seen.add(nm)
                uniq.append(nm)
        return uniq

    async def download_audio(download_url: str, token: str) -> str:
        import tempfile, pathlib

        async with httpx.AsyncClient(timeout=None, follow_redirects=False) as c:
            # Try both header and query param strategies, handle up to 5 redirects
            candidate_urls = [download_url]
            candidate_urls.append(f"{download_url}{'&' if '?' in download_url else '?'}access_token={token}")

            for candidate in candidate_urls:
                url = candidate
                headers = {"Authorization": f"Bearer {token}"} if candidate is download_url else {}
                for _ in range(5):
                    r = await c.get(url, headers=headers)
                    if r.status_code == 200:
                        fd, path = tempfile.mkstemp(suffix=".m4a")
                        pathlib.Path(path).write_bytes(r.content)
                        return path
                    if r.status_code in (301, 302, 303, 307, 308):
                        loc = r.headers.get("location")
                        logger.info("Following redirect {} -> {}", r.status_code, loc)
                        if not loc:
                            break
                        # On cross-host redirect, drop Authorization header for safety
                        try:
                            orig_host = httpx.URL(url).host
                            new_host = httpx.URL(loc).host
                        except Exception:
                            orig_host = new_host = None
                        if orig_host != new_host:
                            headers = {}
                        url = loc
                        continue
                    if r.status_code in (401, 403):
                        # Try next candidate strategy
                        break
                    # Other errors
                    r.raise_for_status()
            # If all attempts failed, raise an informative error
            raise HTTPException(status_code=502, detail="Failed to download recording after redirects and auth strategies")

    def _pick_transcript_file(recording_files: list) -> Optional[Dict[str, Any]]:
        """
        Pick the best available transcript/CC file from Zoom recording files.
        Preference order: TRANSCRIPT -> CC -> VTT extension -> TIMELINE (last resort).
        """
        if not recording_files:
            return None
        # Normalize keys
        def file_type(f: Dict[str, Any]) -> str:
            return (f.get("file_type") or f.get("recording_type") or "").upper()
        # Priority picks
        for prefer in ("TRANSCRIPT", "CC"):
            for f in recording_files:
                if file_type(f) == prefer:
                    return f
        # Extension-based fallback
        for f in recording_files:
            url = f.get("download_url", "")
            if url.lower().endswith(".vtt"):
                return f
        # Last resort: timeline
        for f in recording_files:
            if file_type(f) == "TIMELINE":
                return f
        return None

    async def _download_text(download_url: str, token: str) -> Optional[str]:
        """Download a small text-like resource (e.g., VTT/TRANSCRIPT) using Zoom access token."""
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as c:
                # Try header auth first (follow redirects automatically)
                r = await c.get(download_url, headers={"Authorization": f"Bearer {token}"})
                if r.status_code == 200:
                    return r.text
                # Try query param
                r2 = await c.get(f"{download_url}{'&' if '?' in download_url else '?'}access_token={token}")
                if r2.status_code == 200:
                    return r2.text
        except Exception:
            pass
        return None

    def _parse_vtt_time(ts: str) -> Optional[float]:
        try:
            # Support HH:MM:SS.mmm or MM:SS.mmm
            parts = ts.split(":")
            if len(parts) == 3:
                h, m, s = parts
                sec = float(s)
                return int(h) * 3600 + int(m) * 60 + sec
            if len(parts) == 2:
                m, s = parts
                sec = float(s)
                return int(m) * 60 + sec
            return None
        except Exception:
            return None

    def _parse_vtt(vtt_text: str) -> List[Dict[str, Any]]:
        """
        Minimal VTT parser that extracts cues with start/end and text.
        Attempts to extract a speaker name if cue text begins with "Name:".
        Returns list of {start: float, end: float, text: str, name: Optional[str]}
        """
        segments: List[Dict[str, Any]] = []
        if not vtt_text:
            return segments
        lines = vtt_text.splitlines()
        i = 0
        # Skip WEBVTT header if present
        if i < len(lines) and lines[i].strip().upper().startswith("WEBVTT"):
            i += 1
        # Accept HH:MM:SS.mmm or MM:SS.mmm on either side
        time_pat = re.compile(r"^((?:\d{2}:)?\d{2}:\d{2}\.\d{3})\s+-->\s+((?:\d{2}:)?\d{2}:\d{2}\.\d{3})")
        while i < len(lines):
            line = lines[i].strip()
            i += 1
            if not line:
                continue
            # Optional cue id line (numeric or any)
            if not time_pat.match(line) and i < len(lines):
                # Peek next; if next is time, treat this as cue id and continue
                if not time_pat.match(lines[i].strip() if i < len(lines) else ""):
                    # Skip until time line
                    continue
                else:
                    line = lines[i].strip(); i += 1
            m = time_pat.match(line)
            if not m:
                continue
            start = _parse_vtt_time(m.group(1))
            end = _parse_vtt_time(m.group(2))
            text_lines: List[str] = []
            while i < len(lines) and lines[i].strip():
                text_lines.append(lines[i].rstrip())
                i += 1
            # Skip the blank line after cue
            while i < len(lines) and not lines[i].strip():
                i += 1
            name: Optional[str] = None
            text = " ".join(t.strip() for t in text_lines if t.strip()).strip()
            # Zoom often prefixes speaker with ">> Name:" - strip leading chevrons
            if text.startswith(">"):
                text = re.sub(r"^\s*>+\s*", "", text)
            # Extract name in format "Name: rest"
            mname = re.match(r"^([^:]{1,60}):\s*(.*)$", text)
            if mname:
                candidate = mname.group(1).strip()
                rest = mname.group(2).strip()
                # Avoid generic diarization labels like Speaker 0
                if not re.match(r"^(?:Speaker|Спикер)\s*\d+$", candidate, re.IGNORECASE):
                    name = candidate
                    text = rest
            if start is not None and end is not None:
                segments.append({"start": start, "end": end, "text": text, "name": name})
        return segments

    def _interval_overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
        return max(0.0, min(a_end, b_end) - max(a_start, b_start))

    def _align_names_by_overlap(diar_segments: List[Dict[str, Any]], vtt_segments: List[Dict[str, Any]], offset_seconds: float = 0.0) -> Dict[str, str]:
        """
        For each diarized segment (with 'speaker', 'start', 'end'), find overlapping VTT cues that have a 'name'.
        Accumulate overlap durations per (speaker_id -> name) and pick the name with the most overlap.
        Returns mapping {speaker_id_str: name}.
        """
        if not diar_segments or not vtt_segments:
            return {}
        # Build name overlap per speaker
        per_speaker: Dict[int, Dict[str, float]] = {}
        for seg in diar_segments:
            s_id = int(seg.get("speaker", 0))
            s_start = float(seg.get("start", 0.0)) + offset_seconds
            s_end = float(seg.get("end", 0.0)) + offset_seconds
            if s_end <= s_start:
                continue
            name_to_dur = per_speaker.setdefault(s_id, {})
            for cue in vtt_segments:
                name = cue.get("name")
                if not name:
                    continue
                c_start = float(cue.get("start", 0.0))
                c_end = float(cue.get("end", 0.0))
                if c_end <= c_start:
                    continue
                ov = _interval_overlap(s_start, s_end, c_start, c_end)
                if ov > 0:
                    name_to_dur[name] = name_to_dur.get(name, 0.0) + ov
        # Pick best name per speaker
        mapping: Dict[str, str] = {}
        for s_id, name_durs in per_speaker.items():
            if not name_durs:
                continue
            best_name = max(name_durs.items(), key=lambda x: x[1])[0]
            mapping[str(s_id)] = best_name
        return mapping

    def _align_with_offset_search(diar_segments: List[Dict[str, Any]], vtt_segments: List[Dict[str, Any]], center_offset_seconds: Optional[float] = None) -> Dict[str, str]:
        """
        Try multiple offsets to account for differences between Zoom transcript time origin and audio-only file.
        Searches offsets in [-30s, +30s] with 0.5s step and picks mapping with maximum total overlap.
        """
        if not diar_segments or not vtt_segments:
            return {}
        best_mapping: Dict[str, str] = {}
        best_score = 0.0
        # Coarse-to-fine: 1s step first, then refine +/- 0.5s around best
        def score_mapping(mp: Dict[str, str]) -> float:
            # Sum durations of selected name per speaker
            total = 0.0
            # Build quick lookup of durations per speaker-name
            per_speaker: Dict[int, Dict[str, float]] = {}
            for seg in diar_segments:
                per_speaker.setdefault(int(seg.get("speaker", 0)), {})
            # Recompute per_speaker durations at offset 0 and reuse _align_names_by_overlap logic would duplicate work
            # Here, we simply count count of mapped speakers as proxy when scoring mapping
            return float(len(mp))
        # Define search window
        if center_offset_seconds is None:
            start_off = -30.0
            end_off = 30.0
        else:
            # Search ±120s around the hint
            start_off = center_offset_seconds - 120.0
            end_off = center_offset_seconds + 120.0
        # Use actual overlap sum as score
        off = start_off
        while off <= end_off:
            mp = _align_names_by_overlap(diar_segments, vtt_segments, offset_seconds=off)
            # Compute total overlap for this mapping
            total_overlap = 0.0
            if mp:
                # Sum overlap for chosen name per speaker
                for seg in diar_segments:
                    s_id = str(int(seg.get("speaker", 0)))
                    name = mp.get(s_id)
                    if not name:
                        continue
                    s_start = float(seg.get("start", 0.0)) + off
                    s_end = float(seg.get("end", 0.0)) + off
                    for cue in vtt_segments:
                        if cue.get("name") != name:
                            continue
                        c_start = float(cue.get("start", 0.0))
                        c_end = float(cue.get("end", 0.0))
                        total_overlap += _interval_overlap(s_start, s_end, c_start, c_end)
            if total_overlap > best_score and mp:
                best_score = total_overlap
                best_mapping = mp
            # step 1.0 seconds
            off += 1.0
        return best_mapping

    async def _find_any_vtt_text(files: List[Dict[str, Any]], token: str) -> Optional[str]:
        """
        Last-resort scan through non-media recording files to find any VTT-like text.
        Avoids fetching large media by filtering likely text types.
        """
        if not files:
            return None
        candidate_types = {"TRANSCRIPT", "CC", "TIMELINE", "CHAT"}
        for f in files:
            ftype = (f.get("file_type") or f.get("recording_type") or "").upper()
            if ftype not in candidate_types:
                continue
            url = f.get("download_url")
            if not url:
                continue
            txt = await _download_text(url, token)
            if txt and txt.strip().upper().startswith("WEBVTT"):
                return txt
        return None

    data: Dict[str, Any] = {}
    files: list = []
    # Try up to 2 attempts; fallback to webhook payload if API errors
    for attempt in range(2):
        try:
            data = await fetch_recording_files(access_token, meeting_uuid)
            files = data.get("recording_files", [])
            break
        except httpx.HTTPStatusError as e:
            # Log response text for diagnostics
            err_text = e.response.text if e.response is not None else str(e)
            logger.error("fetch_recording_files failed (attempt {}): status={} body={}", attempt + 1, getattr(e.response, "status_code", "?"), err_text)
            if recording_files_from_event:
                files = recording_files_from_event
                data = {"topic": topic or "", "start_time": start_time or ""}
                break
            # brief backoff before retry
            await asyncio.sleep(5)

    if not files:
        logger.error("No recording files found for meeting {}", meeting_uuid)
        return
    audio = next((f for f in files if f.get("recording_type") == "audio_only"), None) or files[0]
    token = data.get("download_access_token") or access_token
    path = await download_audio(audio["download_url"], token)

    caption = f"✅ Zoom recording processed\nTopic: {data.get('topic','')}\nStart: {data.get('start_time','')}"
    await send_telegram_audio(chat_id, path, caption)

    # Process transcript and summary using existing services
    try:
        transcription_service = TranscriptionService()
        summarization_service = SummarizationService()
        speaker_service = SpeakerIdentificationService()
        file_service = FileService()

        transcript, diar_segments = await transcription_service.transcribe_with_segments(path)
        if transcript:
            # Try Zoom cloud transcript alignment first (retry briefly if transcript not ready yet)
            aligned_mapping: Dict[str, str] = {}
            try:
                logger.info("Attempting Zoom transcript alignment for meeting {}", meeting_uuid[:10])
                max_tries = 6  # ~60 seconds total if transcript is still being generated
                for attempt in range(1, max_tries + 1):
                    tfile = _pick_transcript_file(files)
                    if tfile:
                        logger.info("Found transcript/CC file on attempt {}", attempt)
                        vtt_text = await _download_text(tfile.get("download_url", ""), token)
                        if vtt_text:
                            vtt_segments = _parse_vtt(vtt_text)
                            logger.info("Parsed {} VTT cues", len(vtt_segments))
                            if vtt_segments:
                                # Try direct alignment and with offset search; center search around offset hint if available
                                offset_hint: Optional[float] = None
                                try:
                                    # Prefer difference between audio recording start and meeting start
                                    meeting_start_iso = data.get("start_time") or start_time or ""
                                    audio_start_iso = (audio or {}).get("recording_start") or ""
                                    if meeting_start_iso and audio_start_iso:
                                        from datetime import datetime, timezone
                                        def _parse_iso(s: str) -> Optional[float]:
                                            try:
                                                dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
                                                return dt.replace(tzinfo=dt.tzinfo or timezone.utc).timestamp()
                                            except Exception:
                                                return None
                                        mt = _parse_iso(meeting_start_iso)
                                        at = _parse_iso(audio_start_iso)
                                        if mt is not None and at is not None:
                                            offset_hint = at - mt
                                    # Fallback: if VTT cues start far from zero, use that as hint
                                    if offset_hint is None and vtt_segments:
                                        try:
                                            first_cue_start = float(min(c.get("start", 0.0) for c in vtt_segments))
                                            if first_cue_start > 60.0:
                                                offset_hint = first_cue_start
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                                aligned_mapping = _align_names_by_overlap(diar_segments or [], vtt_segments)
                                if not aligned_mapping:
                                    aligned_mapping = _align_with_offset_search(
                                        diar_segments or [], vtt_segments, center_offset_seconds=offset_hint
                                    )
                                logger.info("Aligned {} speakers via overlap", len(aligned_mapping))
                                break
                    if attempt < max_tries:
                        logger.info("Transcript not ready yet; retrying ({}/{})...", attempt, max_tries)
                        await asyncio.sleep(10)
                        try:
                            data = await fetch_recording_files(access_token, meeting_uuid)
                            files = data.get("recording_files", [])
                            token = data.get("download_access_token") or token
                        except Exception as e2:
                            logger.warning(f"Re-fetch recording files failed: {e2}")
                if aligned_mapping:
                    try:
                        aligned_mapping = speaker_service._disambiguate_speaker_names(aligned_mapping)  # type: ignore[attr-defined]
                    except Exception:
                        pass
                    transcript = speaker_service.replace_speaker_labels(transcript, aligned_mapping)
            except Exception as e:
                logger.warning(f"Zoom transcript alignment failed: {e}")

            # Try applying Zoom participant names to the transcript before saving
            if not aligned_mapping:
                zoom_names: list[str] = []
                try:
                    zoom_names = await fetch_meeting_participants(access_token, meeting_uuid)
                except Exception as e:
                    logger.warning(f"Failed to fetch Zoom participants: {e}")
                if zoom_names:
                    try:
                        transcript = await speaker_service.process_transcript_with_speaker_names(
                            transcript,
                            external_candidate_names=zoom_names,
                            prefer_external=True,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to apply Zoom speaker names: {e}")
            # Save and send transcript file
            timestamp = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
            transcript_filename = f"transcript_{timestamp}.txt"
            transcript_file_path = await file_service.create_text_file(transcript, transcript_filename)
            await send_telegram_document(chat_id, transcript_file_path, f"📄 Transcript from Zoom: {data.get('topic','')}")

            # Create and send summary
            summary = await summarization_service.create_summary_with_action_points(transcript)
            if summary:
                await send_long_message(chat_id, f"📋 Summary & Action Points\n\n{summary}")
        else:
            await send_message(chat_id, "⚠️ Could not create transcript from Zoom recording.")
    except Exception as e:
        # Best-effort; continue even if summarization fails
        await send_message(chat_id, f"⚠️ Post-processing error: {e}")


async def send_telegram_audio(chat_id: int, path: str, caption: str) -> None:
    import httpx

    settings = get_settings()
    token = settings.telegram_bot_token
    api = f"https://api.telegram.org/bot{token}/sendAudio"
    files = {"audio": open(path, "rb")}
    data = {"chat_id": chat_id, "caption": caption}
    async with httpx.AsyncClient(timeout=None) as c:
        r = await c.post(api, data=data, files=files)
        r.raise_for_status()


async def send_telegram_document(chat_id: int, path: str, caption: str) -> None:
    import httpx

    settings = get_settings()
    token = settings.telegram_bot_token
    api = f"https://api.telegram.org/bot{token}/sendDocument"
    files = {"document": open(path, "rb")}
    data = {"chat_id": chat_id, "caption": caption}
    async with httpx.AsyncClient(timeout=None) as c:
        r = await c.post(api, data=data, files=files)
        r.raise_for_status()


async def send_message(chat_id: int, text: str) -> None:
    import httpx

    settings = get_settings()
    token = settings.telegram_bot_token
    api = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.post(api, data=data)
        r.raise_for_status()


def _split_message(message: str, max_length: int = 4000) -> List[str]:
    if len(message) <= max_length:
        return [message]
    chunks: List[str] = []
    current_chunk = ""
    for line in message.split("\n"):
        if len(current_chunk) + len(line) + 1 <= max_length:
            current_chunk += line + "\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.rstrip())
            current_chunk = line + "\n"
    if current_chunk:
        chunks.append(current_chunk.rstrip())
    return chunks


async def send_long_message(chat_id: int, text: str) -> None:
    for chunk in _split_message(text):
        await send_message(chat_id, chunk)


@app.post("/webhooks/zoom/deauth")
async def zoom_deauth(request: Request) -> JSONResponse:
    settings = get_settings()
    raw = await request.body()
    if not verify_signature(request.headers, raw, settings.zoom_webhook_secret):
        raise HTTPException(status_code=401, detail="bad signature")
    body = await request.json()
    zoom_user_id = body.get("payload", {}).get("user_id")
    if zoom_user_id:
        with get_conn(settings.zoom_db_path) as conn:
            delete_connection(conn, zoom_user_id)
    return JSONResponse({"ok": True})


@app.get("/status")
async def status() -> Dict[str, Any]:
    return {"ok": True}


@app.get("/webhooks/zoom")
async def zoom_webhook_get() -> JSONResponse:
    # Some validators probe with GET
    logger.info("Zoom webhook GET probe received")
    return JSONResponse({"ok": True})


