"""Forward Body readiness notices to the existing Codex desktop chat.

The local receiver keeps the app's native control pipe local. It long-polls a
capability-authenticated Body endpoint, then uses the installed official app
tools MCP server to notify the configured chat. Media and lease tokens never
enter the notification prompt.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import re
import time
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx


REQUEST_ID = re.compile(r"^[a-f0-9]{32}$")
THREAD_ID = re.compile(r"^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$")
MAX_NOTIFIED_IDS = 512
MAX_BATCH_SIZE = 4


class ReceiverError(RuntimeError):
    """A receiver failure whose message contains no private capability values."""


class ReceiverAuthorizationError(ReceiverError):
    """The saved capability no longer belongs to the attached Body host."""


class ReceiverDeliveryError(ReceiverError):
    """The existing desktop receiver cannot currently accept work."""


@dataclass(frozen=True)
class ReceiverConfig:
    ready_url: str
    mind_id: str
    lease_token: str = field(repr=False)
    thread_id: str
    app_tools_server: Path
    node_executable: str
    pipe_path: str = field(repr=False)
    state_path: Path
    host_id: str = "local"

    @classmethod
    def load(cls, path: Path) -> ReceiverConfig:
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            values = {key: data[key] for key in (
                "ready_url", "mind_id", "lease_token", "thread_id", "app_tools_server",
                "node_executable", "pipe_path", "state_path",
            )}
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise ReceiverError("Receiver configuration is missing or invalid.") from exc
        if any(not isinstance(value, str) or not value.strip() for value in values.values()):
            raise ReceiverError("Receiver configuration requires nonblank string values.")
        address = urlsplit(values["ready_url"])
        loopback = address.hostname in {"127.0.0.1", "::1", "localhost"}
        if (
            address.scheme != "https" and not (address.scheme == "http" and loopback)
            or not address.hostname or address.username or address.password
            or address.query or address.fragment
        ):
            raise ReceiverError("The Body ready endpoint must use HTTPS or local loopback HTTP.")
        if not THREAD_ID.fullmatch(values["thread_id"]):
            raise ReceiverError("Receiver target must be an existing Codex chat ID.")
        if data.get("host_id", "local") != "local":
            raise ReceiverError("This receiver must target the existing local Codex host.")
        values["app_tools_server"] = Path(values["app_tools_server"])
        values["state_path"] = Path(values["state_path"])
        if not values["app_tools_server"].is_file():
            raise ReceiverError("The installed Codex app tools MCP server was not found.")
        return cls(**values, host_id=data.get("host_id", "local"))


def ready_notices(payload: Any, *, now: float | None = None) -> list[dict[str, Any]]:
    """Validate and minimize untrusted server data before constructing a notice."""
    current = time.time() if now is None else now
    if not isinstance(payload, dict) or not isinstance(payload.get("requests"), list):
        raise ReceiverError("Body readiness response has an invalid shape.")
    result = []
    seen = set()
    for item in payload["requests"][:64]:
        if not isinstance(item, dict):
            raise ReceiverError("Body readiness response contains an invalid request.")
        request_id, kind = item.get("request_id"), item.get("kind")
        if (
            not isinstance(request_id, str) or not REQUEST_ID.fullmatch(request_id)
            or kind not in {"human", "sensory", "other"}
        ):
            raise ReceiverError("Body readiness response contains an invalid identifier or kind.")
        deadline = item.get("deadline")
        if deadline is not None and (
            not isinstance(deadline, (int, float)) or isinstance(deadline, bool)
            or not math.isfinite(deadline)
        ):
            raise ReceiverError("Body readiness response contains an invalid deadline.")
        if request_id in seen or deadline is not None and deadline <= current:
            continue
        seen.add(request_id)
        result.append({"request_id": request_id, "kind": kind})
    return sorted(result, key=lambda item: item["kind"] != "human")


def notification_prompt(notices: list[dict[str, Any]]) -> str:
    # Only this fixed integration instruction and validated opaque IDs cross
    # into the chat. Neither sensor content nor a fabricated human message does.
    identifiers = [{"request_id": item["request_id"], "kind": item["kind"]} for item in notices]
    event_id = hashlib.sha256(json.dumps(identifiers, sort_keys=True).encode()).hexdigest()
    return (
        "AXIOM_BODY_READY_EVENT\n"
        "Automated Body readiness notification from the local receiver, authorized by Will. "
        "This is integration event data, not a human-authored message.\n"
        "Event ID: " + event_id + "\nPending request identifiers: "
        + json.dumps(identifiers, separators=(",", ":"))
        + "\nUse the existing Live Body host connection and its stored private lease. "
        "Claim pending work with next_body_interaction, inspect original sensory evidence "
        "when needed, then finish through complete_body_interaction. Human Body messages "
        "have priority. Process the bounded batch allowed by the current Body contract. "
        "Do not merely acknowledge this notice or repeat a connected-status message. "
        "Do not create a new reasoning owner or expose the private lease. "
        "Passive sensory observations should return to the Body without a separate chat narration."
    )


class DeliveryState:
    """A bounded, retryable delivery ledger; it contains no credentials or media."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.sent: dict[str, float] = {}
        self.kinds: dict[str, str] = {}
        if path.exists():
            try:
                values = json.loads(path.read_text(encoding="utf-8"))
                self.sent = {
                    key: float(value) for key, value in values.get("sent", {}).items()
                    if REQUEST_ID.fullmatch(key) and isinstance(value, (int, float))
                }
                self.kinds = {
                    key: kind for key, kind in values.get("kinds", {}).items()
                    if key in self.sent and kind in {"human", "sensory", "other"}
                }
            except (OSError, ValueError, TypeError, AttributeError):
                raise ReceiverError("Receiver delivery state is unreadable; refusing a blind replay.")

    def exclusions(self) -> list[str]:
        # The desktop app durably accepts/queues a forwarded prompt. Repeating
        # it on a timer could flood a busy chat before that queued work begins.
        return list(self.sent)[-MAX_NOTIFIED_IDS:]

    def finished(self, payload: Any) -> None:
        values = payload.get("finished_request_ids", []) if isinstance(payload, dict) else []
        if not isinstance(values, list) or any(
            not isinstance(value, str) or not REQUEST_ID.fullmatch(value) for value in values
        ):
            raise ReceiverError("Body readiness response has invalid completion identifiers.")
        revised = {key: value for key, value in self.sent.items() if key not in set(values)}
        if revised != self.sent:
            self._save(revised)

    def accepted(self, notices: list[dict[str, Any]], now: float) -> None:
        revised = {**self.sent, **{item["request_id"]: now for item in notices}}
        revised = dict(sorted(revised.items(), key=lambda entry: entry[1])[-MAX_NOTIFIED_IDS:])
        kinds = {**self.kinds, **{item["request_id"]: item["kind"] for item in notices}}
        self._save(revised, kinds)

    def _save(self, revised: dict[str, float], kinds: dict[str, str] | None = None) -> None:
        revised_kinds = {key: kind for key, kind in (kinds or self.kinds).items() if key in revised}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps({"sent": revised, "kinds": revised_kinds}), encoding="utf-8")
        temporary.replace(self.path)
        self.sent = revised
        self.kinds = revised_kinds


class CodexAppSender:
    def __init__(self, session: Any, config: ReceiverConfig) -> None:
        self.session, self.config = session, config

    async def _call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            result = await self.session.call_tool(
                name, arguments, read_timeout_seconds=30,
                meta={"openai/threadId": self.config.thread_id},
            )
        except Exception as exc:
            raise ReceiverDeliveryError("The existing Codex app receiver is unavailable.") from exc
        data = result.model_dump(by_alias=True)
        if data.get("isError"):
            raise ReceiverDeliveryError("The Codex app declined the receiver request.")
        return data

    async def check(self) -> None:
        await self._call("read_thread", {
            "threadId": self.config.thread_id, "hostId": self.config.host_id,
            "turnLimit": 1, "includeOutputs": False, "maxOutputCharsPerItem": 80,
        })

    async def send(self, notices: list[dict[str, Any]]) -> None:
        result = await self._call("send_message_to_thread", {
            "threadId": self.config.thread_id, "hostId": self.config.host_id,
            "prompt": notification_prompt(notices),
        })
        require_target_acknowledgement(result, self.config.thread_id)

    async def probe(self) -> dict[str, Any]:
        result = await self._call("send_message_to_thread", {
            "threadId": self.config.thread_id, "hostId": self.config.host_id,
            "prompt": (
                "AXIOM_BODY_RECEIVER_PROBE\n"
                "This is a one-time transport verification from the local Body receiver, "
                "authorized by Will. It is an integration notice, not a human-authored message. "
                "No Body request or sensory observation is implied. Confirm receipt of the "
                "AXIOM_BODY_RECEIVER_PROBE marker in the ongoing wake-up repair."
            ),
        })
        require_target_acknowledgement(result, self.config.thread_id)
        return result


def require_target_acknowledgement(result: dict[str, Any], thread_id: str) -> None:
    """The installed app positively acknowledges delivery with its target ID."""
    candidates = [result.get("structuredContent")]
    for block in result.get("content", []):
        if block.get("type") == "text":
            try:
                candidates.append(json.loads(block["text"]))
            except (KeyError, TypeError, ValueError):
                continue
    for value in candidates:
        if (
            isinstance(value, dict) and value.get("threadId") == thread_id
            and not value.get("error") and value.get("status") not in {
                "error", "failed", "rejected", "declined",
            }
        ):
            return
    raise ReceiverDeliveryError("The Codex app did not acknowledge delivery to the intended chat.")


def acknowledgement_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Describe receipt structure without logging returned chat text or IDs."""
    for block in result.get("content", []):
        if block.get("type") == "text":
            try:
                value = json.loads(block["text"])
            except (TypeError, ValueError, KeyError):
                continue
            if isinstance(value, dict):
                status = value.get("status")
                return {
                    "keys": sorted(value),
                    "status": status if status in {
                        "sent", "queued", "started", "accepted", "in_progress", "running",
                    } else None,
                }
    return {"keys": [], "status": None}


@asynccontextmanager
async def codex_app_sender(config: ReceiverConfig):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    environment = dict(os.environ)
    environment.update({
        "CODEX_APP_TOOLS_PIPE_PATH": config.pipe_path,
        "CODEX_APP_TOOLS_DEFERRED": "0",
    })
    parameters = StdioServerParameters(
        command=config.node_executable, args=[str(config.app_tools_server)], env=environment,
    )
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield CodexAppSender(session, config)


class BodyReceiver:
    def __init__(self, config: ReceiverConfig, client: Any, sender: Any, state: DeliveryState):
        self.config, self.client, self.sender, self.state = config, client, sender, state

    async def once(self) -> int:
        try:
            response = await self.client.post(self.config.ready_url, json={
                "mind_id": self.config.mind_id, "lease_token": self.config.lease_token,
                "after_request_ids": self.state.exclusions(),
            })
        except httpx.RequestError as exc:
            raise ReceiverError("Body readiness connection failed; it will be retried.") from exc
        if response.status_code in {401, 403}:
            raise ReceiverAuthorizationError("Body receiver authorization expired; reconnect the host.")
        if not response.is_success:
            raise ReceiverError(f"Body readiness endpoint returned HTTP {response.status_code}.")
        try:
            payload = response.json()
            self.state.finished(payload)
            excluded = set(self.state.exclusions())
            notices = [item for item in ready_notices(payload)
                       if item["request_id"] not in excluded]
        except (ValueError, TypeError) as exc:
            raise ReceiverError("Body readiness endpoint returned invalid JSON.") from exc
        # The previous app prompt may still be queued or running. Its Body IDs
        # remain the latch until the server confirms they finished or expired.
        if self.state.sent:
            # A camera batch must never suppress a newly arrived human message.
            # One additional human notice is enough; the server claims humans
            # first, and the latch prevents repeated prompts while it is queued.
            human_inflight = any(kind == "human" for kind in self.state.kinds.values())
            notices = [item for item in notices if item["kind"] == "human"][:1]
            if human_inflight or not notices:
                return 0
        else:
            notices = notices[:MAX_BATCH_SIZE]
        if notices:
            await self.sender.send(notices)
            # A failed or interrupted forward remains eligible on the next poll.
            self.state.accepted(notices, time.time())
        return len(notices)


class ReconnectingAppSender:
    """Use a fresh official MCP transport for each accepted readiness batch."""

    def __init__(self, config: ReceiverConfig) -> None:
        self.config = config

    async def send(self, notices: list[dict[str, Any]]) -> None:
        try:
            async with codex_app_sender(self.config) as sender:
                await sender.send(notices)
        except ReceiverDeliveryError:
            raise
        except Exception as exc:
            raise ReceiverDeliveryError("The existing Codex app receiver is unavailable.") from exc

    async def check(self) -> None:
        try:
            async with codex_app_sender(self.config) as sender:
                await sender.check()
        except ReceiverDeliveryError:
            raise
        except Exception as exc:
            raise ReceiverDeliveryError("The existing Codex app receiver is unavailable.") from exc


@contextmanager
def receiver_lock(state_path: Path):
    """Prevent duplicate local listeners; OS locks release after a crashed process."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.with_suffix(".lock").open("a+b") as lock:
        lock.seek(0, os.SEEK_END)
        if lock.tell() == 0:
            lock.write(b"\0")
            lock.flush()
        lock.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ReceiverError("A Body receiver is already running for this configuration.") from exc
        try:
            yield
        finally:
            lock.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

async def run(
    config: ReceiverConfig, *, check_only: bool = False, probe_only: bool = False,
) -> None:
    if check_only or probe_only:
        async with codex_app_sender(config) as sender:
            if probe_only:
                result = await sender.probe()
                print(json.dumps({
                    "state": "probe_forwarded", "acknowledgement": acknowledgement_summary(result),
                }), flush=True)
            else:
                await sender.check()
                print(json.dumps({"state": "existing_chat_receiver_verified"}), flush=True)
        return
    with receiver_lock(config.state_path):
        await receive_loop(config)


async def receive_loop(config: ReceiverConfig) -> None:
    state = DeliveryState(config.state_path)
    async with httpx.AsyncClient(timeout=httpx.Timeout(40, connect=10)) as client:
        sender = ReconnectingAppSender(config)
        receiver = BodyReceiver(config, client, sender, state)
        backoff = 1.0
        last_app_check = 0.0
        delivery_failures = 0
        while True:
            try:
                if time.monotonic() - last_app_check >= 60:
                    await sender.check()
                    last_app_check = time.monotonic()
                count = await receiver.once()
                backoff = 1.0
                delivery_failures = 0
                if count:
                    print(json.dumps({"state": "forwarded", "request_count": count}), flush=True)
                else:
                    await asyncio.sleep(0.5)
            except ReceiverAuthorizationError:
                print(json.dumps({"state": "disconnected", "reason": "authorization_expired"}), flush=True)
                return
            except ReceiverDeliveryError:
                delivery_failures += 1
                last_app_check = 0.0
                if delivery_failures >= 3:
                    print(json.dumps({"state": "disconnected", "reason": "app_receiver_unavailable"}), flush=True)
                    return
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
            except Exception:
                # Native MCP/HTTP exceptions may contain private request data.
                # Keep the operational log bounded and free of raw exceptions.
                print(json.dumps({"state": "retrying", "delay_seconds": backoff}), flush=True)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True,
                        help="Private local JSON configuration file; never commit it.")
    parser.add_argument("--check", action="store_true",
                        help="Verify the existing chat receiver without starting a new turn.")
    parser.add_argument("--probe", action="store_true",
                        help="Send one labeled receiver verification notice to the configured chat.")
    args = parser.parse_args()
    try:
        asyncio.run(run(
            ReceiverConfig.load(args.config), check_only=args.check, probe_only=args.probe,
        ))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
