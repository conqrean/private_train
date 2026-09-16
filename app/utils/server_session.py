# -*- coding: utf-8 -*-
"""Encrypted server-side session storage.

Flask's default session puts the entire session payload in the cookie, signed
but *not* encrypted, with no expiry - so closing the browser threw away the
login state and the registered card together, and anyone holding the cookie
could read the card number and the account password straight out of it.

Here the cookie carries only a signed random session id; the payload lives on
the server under .run/sessions/, encrypted with AES-256-GCM using a key kept in
.run/session.key (0600). Both paths are already gitignored.
"""
import os
import secrets
import sys
import time
import hashlib
from datetime import timedelta
from pathlib import Path
from typing import Optional

from flask.json.tag import TaggedJSONSerializer
from flask.sessions import SessionInterface, SessionMixin
from itsdangerous import BadSignature, URLSafeTimedSerializer
from werkzeug.datastructures import CallbackDict

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

KEY_SIZE = 32
NONCE_SIZE = 12
TAG_SIZE = 16
SID_SALT = "server-session-id"

_serializer = TaggedJSONSerializer()


def get_state_dir() -> Path:
    """Directory holding runtime state (session store, keys).

    Sits next to the executable when frozen by PyInstaller, otherwise at the
    project root - never inside the temporary _MEIPASS unpack directory, which
    is wiped on exit.
    """
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parents[2]
    state_dir = base / ".run"
    state_dir.mkdir(parents=True, exist_ok=True)
    _restrict(state_dir)
    return state_dir


def _restrict(path: Path, mode: int = 0o700) -> None:
    """Tighten permissions, ignoring platforms that do not support it."""
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def _write_private(path: Path, data: bytes) -> None:
    """Write atomically, readable only by the owner.

    The temporary name carries the pid and random bytes because the app serves
    requests on threads: two concurrent requests for the same session would
    otherwise share one temp path, and whichever renamed second would fail with
    ENOENT after the first had already moved it away.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _load_or_create_hex(path: Path, size: int) -> bytes:
    """Return the secret stored at path, creating it on first run."""
    if path.exists():
        try:
            raw = bytes.fromhex(path.read_text().strip())
            if len(raw) == size:
                return raw
        except (ValueError, OSError):
            pass  # corrupt or unreadable - regenerate below
    raw = get_random_bytes(size)
    _write_private(path, raw.hex().encode())
    return raw


def load_or_create_secret_key(state_dir: Path) -> str:
    """Persistent Flask signing key.

    Replaces the key that used to be hardcoded in this (public) repository, so
    session cookies can no longer be forged by anyone who reads the source.
    Persisting it keeps logins alive across app restarts.
    """
    return _load_or_create_hex(state_dir / "secret.key", KEY_SIZE).hex()


class ServerSession(CallbackDict, SessionMixin):
    """Session dict that tracks whether it was touched during the request."""

    def __init__(self, initial=None, sid: str = "", new: bool = False):
        def on_update(_self):
            _self.modified = True

        CallbackDict.__init__(self, initial, on_update)
        self.sid = sid
        self.new = new
        self.modified = False


class EncryptedFileSessionInterface(SessionInterface):
    """Keeps session payloads on disk, encrypted; cookie holds only the id."""

    session_class = ServerSession

    def __init__(self, state_dir: Path, lifetime: timedelta):
        self.store = state_dir / "sessions"
        self.store.mkdir(parents=True, exist_ok=True)
        _restrict(self.store)
        self.key = _load_or_create_hex(state_dir / "session.key", KEY_SIZE)
        self.lifetime = lifetime
        self._last_prune = 0.0

    # -- helpers ------------------------------------------------------
    def _signer(self, app) -> URLSafeTimedSerializer:
        return URLSafeTimedSerializer(app.secret_key, salt=SID_SALT)

    def _path(self, sid: str) -> Path:
        # Name files by a hash of the id so a directory listing cannot be
        # replayed as a cookie value.
        return self.store / (hashlib.sha256(sid.encode()).hexdigest() + ".bin")

    @staticmethod
    def _new_sid() -> str:
        return secrets.token_urlsafe(32)

    def _load(self, sid: str) -> Optional[dict]:
        path = self._path(sid)
        try:
            blob = path.read_bytes()
        except OSError:
            return None
        if len(blob) < NONCE_SIZE + TAG_SIZE:
            return None

        nonce = blob[:NONCE_SIZE]
        tag = blob[NONCE_SIZE:NONCE_SIZE + TAG_SIZE]
        ciphertext = blob[NONCE_SIZE + TAG_SIZE:]
        try:
            cipher = AES.new(self.key, AES.MODE_GCM, nonce=nonce)
            cipher.update(sid.encode())  # bind the payload to its session id
            payload = _serializer.loads(
                cipher.decrypt_and_verify(ciphertext, tag).decode("utf-8")
            )
        except (ValueError, KeyError, TypeError, UnicodeDecodeError):
            return None  # wrong key, tampered, or written by an older format

        if not isinstance(payload, dict) or payload.get("exp", 0) < time.time():
            path.unlink(missing_ok=True)
            return None
        data = payload.get("data")
        return data if isinstance(data, dict) else None

    def _store_payload(self, session: ServerSession) -> None:
        raw = _serializer.dumps({
            "data": dict(session),
            "exp": time.time() + self.lifetime.total_seconds(),
        }).encode("utf-8")

        nonce = get_random_bytes(NONCE_SIZE)
        cipher = AES.new(self.key, AES.MODE_GCM, nonce=nonce)
        cipher.update(session.sid.encode())
        ciphertext, tag = cipher.encrypt_and_digest(raw)
        _write_private(self._path(session.sid), nonce + tag + ciphertext)

    def _prune(self) -> None:
        """Drop expired session files; runs at most hourly."""
        now = time.time()
        if now - self._last_prune < 3600:
            return
        self._last_prune = now
        cutoff = now - self.lifetime.total_seconds()
        for path in self.store.glob("*.bin"):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)
            except OSError:
                pass
        # Orphaned temp files from a write that died mid-flight. Each carries a
        # unique suffix, so nothing would ever reclaim them otherwise.
        for path in self.store.glob("*.tmp"):
            try:
                if path.stat().st_mtime < now - 3600:
                    path.unlink(missing_ok=True)
            except OSError:
                pass

    # -- SessionInterface ---------------------------------------------
    def open_session(self, app, request) -> ServerSession:
        cookie = request.cookies.get(self.get_cookie_name(app))
        if not cookie:
            return self.session_class(sid=self._new_sid(), new=True)
        try:
            sid = self._signer(app).loads(
                cookie, max_age=int(self.lifetime.total_seconds())
            )
        except BadSignature:
            return self.session_class(sid=self._new_sid(), new=True)

        data = self._load(sid)
        if data is None:
            return self.session_class(sid=self._new_sid(), new=True)
        return self.session_class(data, sid=sid, new=False)

    def save_session(self, app, session, response) -> None:
        name = self.get_cookie_name(app)
        domain = self.get_cookie_domain(app)
        path = self.get_cookie_path(app)

        # Nothing worth persisting: a visitor who never logged in, or a session
        # just emptied by logout. Such a session is not literally empty - every
        # request sets the `_permanent` flag, and merely reading auth state
        # seeds auth/credentials/search_state/cards with empty dicts - so test
        # for meaningful content instead of for an empty mapping. Otherwise
        # every anonymous hit on the login page would leave a file behind.
        if not any(key != "_permanent" and value for key, value in session.items()):
            if session.sid:
                self._path(session.sid).unlink(missing_ok=True)
            if session.modified and not session.new:
                response.delete_cookie(name, domain=domain, path=path)
            return

        if session.modified or session.new:
            self._store_payload(session)
            self._prune()

        # Re-issue the cookie every response so the 30-day window slides
        # forward while the app is in use.
        response.set_cookie(
            name,
            self._signer(app).dumps(session.sid),
            expires=self.get_expiration_time(app, session),
            httponly=self.get_cookie_httponly(app),
            secure=self.get_cookie_secure(app),
            samesite=self.get_cookie_samesite(app),
            domain=domain,
            path=path,
        )
        response.vary.add("Cookie")
