"""Gemini REST client for concise notification summaries."""

import json
import os
from urllib import error, request
import win32cred
import pywintypes
import win32timezone

MODEL = "gemini-3.5-flash-lite"
WORD_LIMIT = 20
TIMEOUT_SECONDS = 60
_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
_CREDENTIAL_TARGET = "NotificationTray/GeminiApiKey"
_CREDENTIAL_USERNAME = "Gemini API Key"
_PROMPT_PREFIX = (
    "Summarize this notification in one concise sentence. Preserve people, "
    "dates and times, amounts, and requested actions. Return only the summary: "
)


def _get_stored_api_key() -> str:
    try:
        credential = win32cred.CredRead(_CREDENTIAL_TARGET, win32cred.CRED_TYPE_GENERIC)
    except pywintypes.error:
        return ""
    api_key = credential.get("CredentialBlob", "")
    if isinstance(api_key, bytes):
        api_key = api_key.decode("utf-8")
    return api_key.replace("\x00", "").strip() if isinstance(api_key, str) else ""


def get_stored_api_key() -> str:
    """Return the API key saved in Windows Credential Manager, if any."""
    return _get_stored_api_key()


def save_api_key(api_key: str) -> bool:
    """Save an API key in Windows Credential Manager, or remove it when blank."""
    api_key = api_key.strip()
    try:
        if api_key:
            win32cred.CredWrite({
                "Type": win32cred.CRED_TYPE_GENERIC,
                "TargetName": _CREDENTIAL_TARGET,
                "UserName": _CREDENTIAL_USERNAME,
                "CredentialBlob": api_key,
                "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
            }, 0)
        else:
            try:
                win32cred.CredDelete(_CREDENTIAL_TARGET, win32cred.CRED_TYPE_GENERIC, 0)
            except pywintypes.error:
                pass
        return True
    except pywintypes.error as exc:
        print(f"[gemini_summarizer] API key storage failed: {exc}")
        return False


def _get_api_key() -> str:
    return os.environ.get("GEMINI_API_KEY", "").strip() or _get_stored_api_key()


def is_configured() -> bool:
    """Return whether a usable Gemini API key is available."""
    return bool(_get_api_key())


def should_summarize(message: str) -> bool:
    """Return whether a notification body exceeds the summary threshold."""
    return len(message.split()) > WORD_LIMIT


def summarize(message: str) -> str | None:
    """Return a concise Gemini summary, or None when the request cannot complete."""
    api_key = _get_api_key()
    if not api_key:
        return None

    payload = {
        "contents": [{
            "parts": [{"text": f"{_PROMPT_PREFIX}{message}"}],
        }],
        "generationConfig": {
            "thinkingConfig": {
                "thinkingLevel": "low",
                "includeThoughts": False,
            },
            "maxOutputTokens": 512,
        },
    }
    try:
        api_request = request.Request(
            _ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            method="POST",
        )
        with request.urlopen(api_request, timeout=TIMEOUT_SECONDS) as response:
            result = json.load(response)
        for candidate in result.get("candidates", []):
            if not isinstance(candidate, dict):
                continue
            content = candidate.get("content", {})
            if not isinstance(content, dict):
                continue
            for part in content.get("parts", []):
                output_text = part.get("text") if isinstance(part, dict) else None
                if isinstance(output_text, str) and output_text.strip():
                    return output_text.strip()
        return None
    except error.HTTPError as exc:
        try:
            details = exc.read().decode("utf-8", "replace")
        except OSError:
            details = str(exc)
        print(f"[gemini_summarizer] summary failed: HTTP {exc.code}: {details}")
        return None
    except Exception as exc:
        print(f"[gemini_summarizer] summary failed: {exc}")
        return None
