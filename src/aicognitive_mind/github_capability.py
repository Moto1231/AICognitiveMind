from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


class GitHubCapabilityError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitHubCapability:
    token: str
    owner: str
    repo: str
    api_url: str = "https://api.github.com"

    @classmethod
    def from_env(cls) -> "GitHubCapability":
        token = (
            os.getenv("AXIOM_GITHUB_TOKEN", "").strip()
            or os.getenv("GITHUB_TOKEN", "").strip()
        )
        repository = os.getenv(
            "AXIOM_GITHUB_REPOSITORY",
            "Moto1231/AICognitiveMind",
        ).strip()

        if not token:
            raise GitHubCapabilityError(
                "GitHub access is not configured. Set AXIOM_GITHUB_TOKEN "
                "(preferred) or GITHUB_TOKEN."
            )

        if "/" not in repository:
            raise GitHubCapabilityError(
                "AXIOM_GITHUB_REPOSITORY must be in owner/repository form."
            )

        owner, repo = repository.split("/", 1)
        if not owner or not repo:
            raise GitHubCapabilityError(
                "AXIOM_GITHUB_REPOSITORY must be in owner/repository form."
            )

        return cls(
            token=token,
            owner=owner,
            repo=repo,
            api_url=os.getenv(
                "AXIOM_GITHUB_API_URL",
                "https://api.github.com",
            ).rstrip("/"),
        )

    @property
    def _repo_prefix(self) -> str:
        return f"/repos/{quote(self.owner, safe='')}/{quote(self.repo, safe='')}"

    def _request(
        self,
        method: str,
        endpoint: str,
        payload: dict[str, Any] | None = None,
        *,
        allow_404: bool = False,
    ) -> Any:
        body = None
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "Axiom",
        }

        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(
            f"{self.api_url}{endpoint}",
            data=body,
            headers=headers,
            method=method,
        )

        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read()
        except HTTPError as exc:
            raw = exc.read()
            if allow_404 and exc.code == 404:
                return None
            try:
                detail = json.loads(raw.decode("utf-8"))
                message = detail.get("message") or str(detail)
            except Exception:
                message = raw.decode("utf-8", errors="replace")
            raise GitHubCapabilityError(
                f"GitHub API {method} {endpoint} failed ({exc.code}): {message}"
            ) from exc
        except URLError as exc:
            raise GitHubCapabilityError(
                f"GitHub API {method} {endpoint} could not be reached: {exc.reason}"
            ) from exc

        if not raw:
            return None

        return json.loads(raw.decode("utf-8"))

    def status(self) -> dict[str, Any]:
        data = self._request("GET", self._repo_prefix)
        return {
            "repository": data["full_name"],
            "default_branch": data["default_branch"],
            "private": data["private"],
            "permissions": data.get("permissions", {}),
            "html_url": data["html_url"],
        }

    def list_path(self, path: str = "", ref: str | None = None) -> dict[str, Any]:
        clean_path = path.strip("/")
        encoded_path = quote(clean_path, safe="/")
        endpoint = f"{self._repo_prefix}/contents"
        if encoded_path:
            endpoint += f"/{encoded_path}"
        if ref:
            endpoint += "?" + urlencode({"ref": ref})

        data = self._request("GET", endpoint)
        if not isinstance(data, list):
            raise GitHubCapabilityError(
                f"{path or '/'} is not a directory in {self.owner}/{self.repo}."
            )

        return {
            "repository": f"{self.owner}/{self.repo}",
            "path": clean_path,
            "ref": ref,
            "entries": [
                {
                    "name": item.get("name"),
                    "path": item.get("path"),
                    "type": item.get("type"),
                    "sha": item.get("sha"),
                    "size": item.get("size"),
                }
                for item in data
            ],
        }

    def read_file(self, path: str, ref: str | None = None) -> dict[str, Any]:
        clean_path = path.strip("/")
        if not clean_path:
            raise GitHubCapabilityError("path is required.")

        endpoint = f"{self._repo_prefix}/contents/{quote(clean_path, safe='/')}"
        if ref:
            endpoint += "?" + urlencode({"ref": ref})

        data = self._request("GET", endpoint)
        if not isinstance(data, dict) or data.get("type") != "file":
            raise GitHubCapabilityError(
                f"{clean_path} is not a file in {self.owner}/{self.repo}."
            )

        if data.get("encoding") != "base64" or "content" not in data:
            raise GitHubCapabilityError(
                f"GitHub did not return inline Base64 content for {clean_path}."
            )

        try:
            decoded = base64.b64decode(data["content"]).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise GitHubCapabilityError(
                f"{clean_path} is not UTF-8 text. "
                "This first capability slice handles text files."
            ) from exc

        return {
            "repository": f"{self.owner}/{self.repo}",
            "path": clean_path,
            "ref": ref,
            "sha": data.get("sha"),
            "size": data.get("size"),
            "html_url": data.get("html_url"),
            "content": decoded,
        }

    def create_branch(
        self,
        branch: str,
        base_ref: str | None = None,
    ) -> dict[str, Any]:
        clean_branch = branch.strip().removeprefix("refs/heads/")
        if not clean_branch:
            raise GitHubCapabilityError("branch is required.")

        base = (base_ref or self.status()["default_branch"]).strip()
        if not base:
            raise GitHubCapabilityError("base_ref is required.")

        base_data = self._request(
            "GET",
            f"{self._repo_prefix}/git/ref/heads/{quote(base, safe='')}",
        )
        base_object = base_data.get("object", {}) if isinstance(base_data, dict) else {}
        base_sha = base_object.get("sha")
        if not base_sha:
            raise GitHubCapabilityError(
                f"GitHub did not return a commit SHA for base ref {base!r}."
            )

        created = self._request(
            "POST",
            f"{self._repo_prefix}/git/refs",
            {
                "ref": f"refs/heads/{clean_branch}",
                "sha": base_sha,
            },
        )
        object_data = created.get("object", {}) if isinstance(created, dict) else {}

        return {
            "repository": f"{self.owner}/{self.repo}",
            "branch": clean_branch,
            "base_ref": base,
            "sha": object_data.get("sha") or base_sha,
            "ref": created.get("ref") if isinstance(created, dict) else None,
        }

    def create_pull_request(
        self,
        title: str,
        head: str,
        base: str | None = None,
        body: str | None = None,
        draft: bool = False,
    ) -> dict[str, Any]:
        clean_title = title.strip()
        clean_head = head.strip()
        if not clean_title:
            raise GitHubCapabilityError("title is required.")
        if not clean_head:
            raise GitHubCapabilityError("head is required.")

        target_base = (base or self.status()["default_branch"]).strip()
        if not target_base:
            raise GitHubCapabilityError("base is required.")

        payload: dict[str, Any] = {
            "title": clean_title,
            "head": clean_head,
            "base": target_base,
            "draft": draft,
        }
        if body is not None:
            payload["body"] = body

        result = self._request("POST", f"{self._repo_prefix}/pulls", payload)

        return {
            "repository": f"{self.owner}/{self.repo}",
            "number": result.get("number") if isinstance(result, dict) else None,
            "title": result.get("title") if isinstance(result, dict) else clean_title,
            "state": result.get("state") if isinstance(result, dict) else None,
            "draft": result.get("draft") if isinstance(result, dict) else draft,
            "html_url": result.get("html_url") if isinstance(result, dict) else None,
            "head": clean_head,
            "base": target_base,
        }

    def write_file(
        self,
        path: str,
        content: str,
        message: str,
        branch: str | None = None,
    ) -> dict[str, Any]:
        clean_path = path.strip("/")
        if not clean_path:
            raise GitHubCapabilityError("path is required.")
        if not message.strip():
            raise GitHubCapabilityError("commit message is required.")

        encoded_path = quote(clean_path, safe="/")
        content_endpoint = f"{self._repo_prefix}/contents/{encoded_path}"

        lookup_endpoint = content_endpoint
        if branch:
            lookup_endpoint += "?" + urlencode({"ref": branch})

        existing = self._request("GET", lookup_endpoint, allow_404=True)

        payload: dict[str, Any] = {
            "message": message.strip(),
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        }
        if branch:
            payload["branch"] = branch

        if isinstance(existing, dict) and existing.get("sha"):
            payload["sha"] = existing["sha"]

        result = self._request("PUT", content_endpoint, payload)
        commit = result.get("commit", {}) if isinstance(result, dict) else {}
        file_data = result.get("content", {}) if isinstance(result, dict) else {}

        return {
            "repository": f"{self.owner}/{self.repo}",
            "path": clean_path,
            "branch": branch,
            "created": existing is None,
            "content_sha": file_data.get("sha"),
            "commit_sha": commit.get("sha"),
            "commit_url": commit.get("html_url"),
        }
