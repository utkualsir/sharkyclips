"""Encryption at rest for secrets on this computer (the YouTube sign-in token).

The data is encrypted with a random 256-bit key (HMAC-SHA256 in counter mode as the key stream,
plus an HMAC-SHA256 tag; Python's standard library only, no extra package). The key itself is
protected by the operating system:

  Windows  DPAPI (CryptProtectData): only this Windows user on this PC can unwrap it
  macOS    the login Keychain (`security` tool), service "SharkyClips"
  other    a key file readable only by the user (0600)

A copied settings folder therefore can't be used on another PC / account: the token simply
counts as missing there and the user connects again.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import platform
import secrets
import subprocess
from pathlib import Path

from .procs import no_window

MAGIC = "sharkyclips-secret-v1"
KEYCHAIN_SERVICE = "SharkyClips"


class SecretError(Exception):
    pass


# ------------------------------------------------------------------ cipher


def _subkeys(key: bytes) -> tuple[bytes, bytes]:
    return (hmac.new(key, b"enc", hashlib.sha256).digest(), hmac.new(key, b"mac", hashlib.sha256).digest())


def _stream(enc_key: bytes, nonce: bytes, n: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < n:
        out += hmac.new(enc_key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()
        counter += 1
    return bytes(out[:n])


def seal(key: bytes, plain: bytes) -> bytes:
    enc_key, mac_key = _subkeys(key)
    nonce = secrets.token_bytes(16)
    ct = bytes(a ^ b for a, b in zip(plain, _stream(enc_key, nonce, len(plain))))
    tag = hmac.new(mac_key, nonce + ct, hashlib.sha256).digest()
    return nonce + ct + tag


def open_sealed(key: bytes, blob: bytes) -> bytes:
    if len(blob) < 48:
        raise SecretError("too short")
    enc_key, mac_key = _subkeys(key)
    nonce, ct, tag = blob[:16], blob[16:-32], blob[-32:]
    if not hmac.compare_digest(tag, hmac.new(mac_key, nonce + ct, hashlib.sha256).digest()):
        raise SecretError("wrong key or damaged data")
    return bytes(a ^ b for a, b in zip(ct, _stream(enc_key, nonce, len(ct))))


# ------------------------------------------------------------------ OS key protection


def _dpapi(data: bytes, protect: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    ent = ctypes.create_string_buffer(MAGIC.encode(), len(MAGIC))
    entropy = Blob(len(MAGIC), ctypes.cast(ent, ctypes.POINTER(ctypes.c_char)))
    out = Blob()
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    ok = fn(ctypes.byref(blob_in), None, ctypes.byref(entropy), None, None, 0x1,  # UI_FORBIDDEN
            ctypes.byref(out))
    if not ok:
        raise SecretError(f"DPAPI failed ({ctypes.get_last_error()})")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(out.pbData)


def _keychain_enabled() -> bool:
    return platform.system() == "Darwin" and os.environ.get("SHARKYCLIPS_NO_KEYCHAIN") != "1"


def _keychain_get(account: str) -> bytes | None:
    try:
        r = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", account, "-w"],
                           capture_output=True, text=True, timeout=15, **no_window())
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    try:
        return bytes.fromhex(r.stdout.strip())
    except ValueError:
        return None


def _keychain_set(account: str, key: bytes) -> bool:
    try:
        r = subprocess.run(["security", "add-generic-password", "-U", "-s", KEYCHAIN_SERVICE, "-a", account,
                            "-w", key.hex()], capture_output=True, timeout=15, **no_window())
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _keychain_delete(account: str) -> None:
    try:
        subprocess.run(["security", "delete-generic-password", "-s", KEYCHAIN_SERVICE, "-a", account],
                       capture_output=True, timeout=15, **no_window())
    except (OSError, subprocess.SubprocessError):
        pass


def _write_private(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    if os.name != "nt":
        os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def _account(folder: Path) -> str:
    # one Keychain item per settings folder (tests and copies use their own)
    return "key-" + hashlib.sha256(str(folder.resolve()).encode()).hexdigest()[:16]


def _key(folder: Path, create: bool) -> tuple[bytes, str] | None:
    """The master key of this settings sub-folder and how it is protected."""
    dp, plain = folder / "key.dpapi", folder / "key.bin"
    if os.name == "nt":
        if dp.is_file():
            try:
                return _dpapi(dp.read_bytes(), protect=False), "dpapi"
            except (SecretError, OSError):
                if not create:
                    return None
        if create:
            key = secrets.token_bytes(32)
            try:
                _write_private(dp, _dpapi(key, protect=True))
                plain.unlink(missing_ok=True)
                return key, "dpapi"
            except (SecretError, OSError):
                pass  # very unusual (DPAPI blocked): fall back to the user-only key file
    elif _keychain_enabled():
        acct = _account(folder)
        key = _keychain_get(acct)
        if key and len(key) == 32:
            return key, "keychain"
        if create:
            key = secrets.token_bytes(32)
            if _keychain_set(acct, key) and _keychain_get(acct) == key:
                plain.unlink(missing_ok=True)
                return key, "keychain"
    if plain.is_file():
        data = plain.read_bytes()
        if len(data) == 32:
            return data, "file"
    if create:
        key = secrets.token_bytes(32)
        _write_private(plain, key)
        return key, "file"
    return None


# ------------------------------------------------------------------ public API


def save(path: Path, data: dict) -> str:
    """Encrypt `data` (JSON) into `path`. Returns the key protection used."""
    got = _key(path.parent, create=True)
    assert got is not None
    key, how = got
    blob = seal(key, json.dumps(data, ensure_ascii=False).encode("utf-8"))
    env = {"format": MAGIC, "protection": how, "data": base64.b64encode(blob).decode("ascii")}
    _write_private(path, json.dumps(env).encode("utf-8"))
    return how


def load(path: Path) -> dict | None:
    """Decrypt `path`. None if it is missing, damaged or was made on another PC / account."""
    try:
        env = json.loads(path.read_text(encoding="utf-8"))
        if env.get("format") != MAGIC:
            return None
        got = _key(path.parent, create=False)
        if got is None:
            return None
        data = json.loads(open_sealed(got[0], base64.b64decode(env["data"])).decode("utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError, KeyError, SecretError, TypeError):
        return None


def protection(path: Path) -> str | None:
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("protection")
    except (OSError, ValueError, AttributeError):
        return None


def forget_key(folder: Path) -> None:
    """Remove the key (after the secret it protected is gone)."""
    (folder / "key.dpapi").unlink(missing_ok=True)
    (folder / "key.bin").unlink(missing_ok=True)
    if _keychain_enabled():
        _keychain_delete(_account(folder))
