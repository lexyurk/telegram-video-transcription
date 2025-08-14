import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse
from typing import Any, Dict, Optional, List

import httpx
import jwt
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse, PlainTextResponse

from telegram_bot.config import get_settings
from telegram_bot.services.transcription_service import TranscriptionService
from telegram_bot.services.summarization_service import SummarizationService
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


@app.get("/zoom/connect")
async def zoom_connect(telegram_chat_id: int, telegram_user_id: int) -> Dict[str, str]:
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
    try:
        body = json.loads(raw.decode())
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")

    # CRC validation
    if body.get("event") == "endpoint.url_validation":
        plain = body["payload"]["plainToken"]
        digest = hmac.new(settings.zoom_webhook_secret.encode(), plain.encode(), hashlib.sha256).digest()
        enc_b64 = base64.b64encode(digest).decode()
        return JSONResponse({"plainToken": plain, "encryptedToken": enc_b64})

    if not verify_signature(request.headers, raw, settings.zoom_webhook_secret):
        raise HTTPException(status_code=401, detail="bad signature")

    event = body.get("event")
    if event == "recording.completed":
        obj = body["payload"]["object"]
        zoom_user_id = obj["host_id"]
        meeting_uuid = obj["uuid"]

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
        background_tasks.add_task(process_recording, meeting_uuid, zoom_user_id, int(chat_id))
        return JSONResponse({"ok": True})

    return JSONResponse({"ok": True})


async def process_recording(meeting_uuid: str, zoom_user_id: str, chat_id: int) -> None:
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

    async def download_audio(download_url: str, token: str) -> str:
        dl = f"{download_url}?access_token={token}"
        import tempfile, pathlib

        async with httpx.AsyncClient(timeout=None) as c:
            r = await c.get(dl)
            r.raise_for_status()
            fd, path = tempfile.mkstemp(suffix=".m4a")
            pathlib.Path(path).write_bytes(r.content)
            return path

    data = await fetch_recording_files(access_token, meeting_uuid)
    files = data.get("recording_files", [])
    if not files:
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
        file_service = FileService()

        transcript = await transcription_service.transcribe_file(path)
        if transcript:
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
    return JSONResponse({"ok": True})


