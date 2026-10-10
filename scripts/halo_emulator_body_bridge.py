"""Connect Halo emulator button events to Axiom's authenticated Body API.

This is a local development host. It injects a caller-supplied JPEG for LOOK;
the Halo emulator does not provide a camera sensor. Point --base-url at a local
or mock Axiom service while developing so test images stay out of live journals.
"""

from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
MAX_JPEG_BYTES = 5 * 1024 * 1024


class AxiomBodyClient:
    def __init__(self, base_url: str, username: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(CookieJar())
        )
        self.body_session = "halo-emulator-" + uuid.uuid4().hex
        self._request(
            "/v1/portal/login",
            {"username": username, "password": password},
            authenticated=False,
        )

    def observe_jpeg(self, jpeg: bytes, width: int, height: int) -> str:
        image_data_url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
        self._request(
            "/v1/body/eyes/observe",
            {
                "image_data_url": image_data_url,
                "width": width,
                "height": height,
                "source": "brilliant-halo-emulator-test-image",
            },
        )
        result = self._request("/v1/mind/body/see?express=false", None)
        response_text = result.get("response_text")
        if not isinstance(response_text, str) or not response_text.strip():
            raise RuntimeError("Axiom Body returned no response_text")
        return response_text.strip()

    def _request(
        self,
        path: str,
        payload: dict[str, Any] | None,
        *,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if authenticated:
            headers["X-Body-Session"] = self.body_session
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8") if payload is not None else None,
            headers=headers,
            method="POST",
        )
        try:
            with self.opener.open(request, timeout=130) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Axiom Body returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Could not reach Axiom Body: {exc.reason}") from exc
        try:
            decoded = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Axiom Body returned invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise RuntimeError("Axiom Body returned an unexpected response")
        return decoded


def load_jpeg(path: Path) -> tuple[bytes, int, int]:
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - supplied by halo-emulator
        raise RuntimeError("Pillow is required to read the JPEG dimensions") from exc

    jpeg = path.read_bytes()
    if len(jpeg) > MAX_JPEG_BYTES:
        raise ValueError("The Body vision route accepts JPEGs up to 5 MB")
    if not jpeg.startswith(b"\xff\xd8\xff"):
        raise ValueError(f"{path} is not a JPEG file")
    with Image.open(path) as image:
        if image.format != "JPEG":
            raise ValueError(f"{path} is not a JPEG file")
        image.load()
        width, height = image.size
    return jpeg, width, height


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Explicit local/mock Axiom service URL")
    parser.add_argument("--image", required=True, type=Path, help="JPEG fixture used for AXIOM:LOOK")
    parser.add_argument("--username", default=os.environ.get("AXIOM_BODY_USERNAME"))
    args = parser.parse_args()
    parsed_url = urlsplit(args.base_url)
    host = parsed_url.hostname
    if parsed_url.scheme not in {"http", "https"}:
        parser.error("--base-url must use http or https")
    if host not in {"localhost", "127.0.0.1", "::1"}:
        parser.error("--base-url must use localhost, 127.0.0.1, or ::1 to protect live accounts")
    if not args.username:
        args.username = input("Axiom account username: ").strip()
    args.password = os.environ.get("AXIOM_BODY_PASSWORD") or getpass.getpass("Axiom account password: ")
    return args


def main() -> int:
    args = parse_args()
    jpeg, width, height = load_jpeg(args.image)
    from halo_emulator import HaloEmulator

    client = AxiomBodyClient(args.base_url, args.username, args.password)
    with HaloEmulator(print_handler=None) as emulator:
        emulator.load_directory(ROOT / "halo_app")
        emulator.start("main.lua")
        seen = len(emulator.get_bluetooth_sent())
        print("Ready: single press sends the fixture through Axiom Body; Ctrl+C stops.")
        try:
            while emulator.is_running():
                sent = emulator.get_bluetooth_sent()
                for event in sent[seen:]:
                    command = event.decode("utf-8", errors="ignore").strip()
                    if command == "AXIOM:LOOK":
                        try:
                            print("Sending the selected JPEG through /v1/body/eyes/observe and /v1/mind/body/see…")
                            reply = client.observe_jpeg(jpeg, width, height)
                        except Exception as exc:
                            reply = f"Axiom request failed: {exc}"
                        emulator.inject_bluetooth_data(reply.encode("utf-8"))
                    elif command == "AXIOM:LISTEN":
                        emulator.inject_bluetooth_data(b"Halo audio is not connected in this bridge.")
                    elif command == "AXIOM:STATUS":
                        emulator.inject_bluetooth_data(b"Axiom Body bridge is connected.")
                seen = len(sent)
                if emulator.get_error() is not None:
                    raise RuntimeError(f"Halo emulator failed: {emulator.get_error()}")
                time.sleep(0.05)
        except KeyboardInterrupt:
            print("Stopping Halo emulator bridge.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
