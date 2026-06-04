from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from fnmatch import fnmatchcase
import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from kb.security_scan import SecurityScanEntry, scan_text_entries
from kb.service import Citadel

GITHUB_API = "https://api.github.com"
SOURCE_URL_TEMPLATE = "https://github.com/orgs/{org}/repositories"
STATE_VERSION = 1


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _short(value: str | None, *, length: int = 160) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= length:
        return text
    return f"{text[: length - 1]}."


def _matches_any(name: str, patterns: tuple[str, ...]) -> bool:
    candidates = {name, name.split("/")[-1]}
    return any(
        fnmatchcase(candidate, pattern)
        for pattern in patterns
        for candidate in candidates
    )


@dataclass(frozen=True)
class GitHubRepo:
    name: str
    full_name: str
    html_url: str
    description: str | None
    language: str | None
    pushed_at: str | None
    updated_at: str | None
    default_branch: str | None
    visibility: str | None
    archived: bool
    stargazers_count: int
    forks_count: int
    open_issues_count: int
    topics: tuple[str, ...]
    license_name: str | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "GitHubRepo":
        license_data = data.get("license") or {}
        return cls(
            name=str(data.get("name") or ""),
            full_name=str(data.get("full_name") or ""),
            html_url=str(data.get("html_url") or ""),
            description=data.get("description"),
            language=data.get("language"),
            pushed_at=data.get("pushed_at"),
            updated_at=data.get("updated_at"),
            default_branch=data.get("default_branch"),
            visibility=data.get("visibility"),
            archived=bool(data.get("archived")),
            stargazers_count=int(data.get("stargazers_count") or 0),
            forks_count=int(data.get("forks_count") or 0),
            open_issues_count=int(data.get("open_issues_count") or 0),
            topics=tuple(data.get("topics") or ()),
            license_name=license_data.get("name"),
        )

    @property
    def fingerprint(self) -> str:
        parts = [
            self.pushed_at or "",
            self.updated_at or "",
            str(self.open_issues_count),
            self.default_branch or "",
            str(self.archived),
        ]
        return "|".join(parts)

    def state(self) -> dict[str, Any]:
        return {
            "fingerprint": self.fingerprint,
            "pushed_at": self.pushed_at,
            "updated_at": self.updated_at,
            "open_issues_count": self.open_issues_count,
        }

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "full_name": self.full_name,
            "url": self.html_url,
            "description": self.description,
            "language": self.language,
            "pushed_at": self.pushed_at,
            "updated_at": self.updated_at,
            "open_issues_count": self.open_issues_count,
            "stars": self.stargazers_count,
            "forks": self.forks_count,
            "topics": list(self.topics),
            "archived": self.archived,
        }


@dataclass(frozen=True)
class GitHubEvent:
    id: str
    type: str
    repo: str
    actor: str
    created_at: str
    summary: str

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "GitHubEvent":
        event_type = str(data.get("type") or "Event")
        payload = data.get("payload") or {}
        repo = (data.get("repo") or {}).get("name") or "unknown/repository"
        actor = (data.get("actor") or {}).get("login") or "unknown"
        return cls(
            id=str(data.get("id") or ""),
            type=event_type,
            repo=repo,
            actor=actor,
            created_at=str(data.get("created_at") or ""),
            summary=_event_summary(event_type, payload),
        )

    def summary_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "type": self.type,
            "repo": self.repo,
            "actor": self.actor,
            "created_at": self.created_at,
            "summary": self.summary,
        }


@dataclass(frozen=True)
class GitHubCommit:
    repo: str
    sha: str
    html_url: str
    message: str
    authored_at: str | None
    author_name: str | None
    author_login: str | None

    @classmethod
    def from_api(cls, data: dict[str, Any], *, repo: str) -> "GitHubCommit":
        commit = data.get("commit") or {}
        author = commit.get("author") or {}
        github_author = data.get("author") or {}
        message = str(commit.get("message") or "").splitlines()[0]
        return cls(
            repo=repo,
            sha=str(data.get("sha") or ""),
            html_url=str(data.get("html_url") or ""),
            message=_short(message, length=140),
            authored_at=author.get("date"),
            author_name=author.get("name"),
            author_login=github_author.get("login"),
        )

    def summary_dict(self) -> dict[str, str | None]:
        return {
            "repo": self.repo,
            "sha": self.sha[:12],
            "url": self.html_url,
            "message": self.message,
            "authored_at": self.authored_at,
            "author": self.author_login or self.author_name,
        }


@dataclass(frozen=True)
class GitHubPullRequest:
    repo: str
    number: int
    title: str
    html_url: str
    state: str
    draft: bool
    user_login: str | None
    created_at: str | None
    updated_at: str | None
    merged_at: str | None

    @classmethod
    def from_api(cls, data: dict[str, Any], *, repo: str) -> "GitHubPullRequest":
        user = data.get("user") or {}
        return cls(
            repo=repo,
            number=int(data.get("number") or 0),
            title=_short(data.get("title"), length=140) or "(no title)",
            html_url=str(data.get("html_url") or ""),
            state=str(data.get("state") or ""),
            draft=bool(data.get("draft")),
            user_login=user.get("login"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            merged_at=data.get("merged_at"),
        )

    @property
    def is_open(self) -> bool:
        return self.state == "open"

    @property
    def is_merged(self) -> bool:
        return bool(self.merged_at)

    def summary_dict(self) -> dict[str, Any]:
        return {
            "repo": self.repo,
            "number": self.number,
            "title": self.title,
            "url": self.html_url,
            "state": self.state,
            "draft": self.draft,
            "author": self.user_login,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "merged_at": self.merged_at,
        }


class GitHubAPIError(RuntimeError):
    pass


class GitHubOrgClient:
    def __init__(self, *, token: str | None = None, timeout: float = 20.0) -> None:
        self.token = token
        self.timeout = timeout

    def fetch_repos(
        self,
        org: str,
        *,
        max_repos: int,
        include_private: bool = True,
    ) -> list[GitHubRepo]:
        repos: list[GitHubRepo] = []
        per_page = min(max(max_repos, 1), 100)
        page = 1
        while len(repos) < max_repos:
            data = self._get_json(
                f"/orgs/{org}/repos",
                {
                    "type": "all" if include_private else "public",
                    "sort": "pushed",
                    "direction": "desc",
                    "per_page": per_page,
                    "page": page,
                },
            )
            if not isinstance(data, list):
                raise GitHubAPIError("GitHub returned an unexpected repositories payload.")
            repos.extend(GitHubRepo.from_api(item) for item in data)
            if len(data) < per_page:
                break
            page += 1
        return repos[:max_repos]

    def fetch_events(self, org: str, *, max_events: int) -> list[GitHubEvent]:
        events: list[GitHubEvent] = []
        per_page = min(max(max_events, 1), 100)
        page = 1
        while len(events) < max_events:
            data = self._get_json(
                f"/orgs/{org}/events",
                {
                    "per_page": per_page,
                    "page": page,
                },
            )
            if not isinstance(data, list):
                raise GitHubAPIError("GitHub returned an unexpected events payload.")
            events.extend(GitHubEvent.from_api(item) for item in data)
            if len(data) < per_page:
                break
            page += 1
        return events[:max_events]

    def fetch_commits(self, repo: GitHubRepo, *, max_commits: int) -> list[GitHubCommit]:
        if max_commits <= 0:
            return []
        params: dict[str, Any] = {
            "per_page": min(max(max_commits, 1), 100),
        }
        if repo.default_branch:
            params["sha"] = repo.default_branch
        data = self._get_json(f"/repos/{quote(repo.full_name, safe='/')}/commits", params)
        if not isinstance(data, list):
            raise GitHubAPIError("GitHub returned an unexpected commits payload.")
        return [GitHubCommit.from_api(item, repo=repo.full_name) for item in data[:max_commits]]

    def fetch_pull_requests(
        self,
        repo: GitHubRepo,
        *,
        max_pull_requests: int,
    ) -> list[GitHubPullRequest]:
        if max_pull_requests <= 0:
            return []
        data = self._get_json(
            f"/repos/{quote(repo.full_name, safe='/')}/pulls",
            {
                "state": "all",
                "sort": "updated",
                "direction": "desc",
                "per_page": min(max(max_pull_requests, 1), 100),
            },
        )
        if not isinstance(data, list):
            raise GitHubAPIError("GitHub returned an unexpected pull requests payload.")
        return [
            GitHubPullRequest.from_api(item, repo=repo.full_name)
            for item in data[:max_pull_requests]
        ]

    def _get_json(self, path: str, params: dict[str, Any]) -> Any:
        query = urlencode(params)
        request = Request(
            f"{GITHUB_API}{path}?{query}",
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "citadel-archive-github-sync",
                "X-GitHub-Api-Version": "2022-11-28",
                **({"Authorization": f"Bearer {self.token}"} if self.token else {}),
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise GitHubAPIError(f"GitHub API returned {exc.code}: {detail}") from exc
        except URLError as exc:
            raise GitHubAPIError(f"Could not reach GitHub API: {exc.reason}") from exc


class GitHubOrgSyncer:
    def __init__(
        self,
        citadel: Citadel,
        *,
        org: str | None = None,
        client: GitHubOrgClient | None = None,
        state_path: str | Path | None = None,
        max_repos: int | None = None,
        max_events: int | None = None,
        max_commits_per_repo: int | None = None,
        max_pull_requests_per_repo: int | None = None,
        include_commits: bool | None = None,
        ingest_unchanged: bool | None = None,
        run_improve: bool | None = None,
    ) -> None:
        self.citadel = citadel
        self.config = citadel.config
        self.org = org or self.config.github_org
        self.client = client or GitHubOrgClient(token=self.config.github_token)
        self.state_path = Path(state_path or self.config.github_sync_state_path)
        self.max_repos = max_repos or self.config.github_sync_max_repos
        self.max_events = max_events or self.config.github_sync_max_events
        self.max_commits_per_repo = (
            self.config.github_sync_max_commits_per_repo
            if max_commits_per_repo is None
            else max_commits_per_repo
        )
        self.max_pull_requests_per_repo = (
            self.config.github_sync_max_pull_requests_per_repo
            if max_pull_requests_per_repo is None
            else max_pull_requests_per_repo
        )
        self.include_commits = (
            self.config.github_sync_include_commits if include_commits is None else include_commits
        )
        self.ingest_unchanged = (
            self.config.github_sync_ingest_unchanged
            if ingest_unchanged is None
            else ingest_unchanged
        )
        self.run_improve = self.config.github_sync_run_improve if run_improve is None else run_improve
        self.include_private = self.config.github_sync_include_private
        self.repo_allowlist = self.config.github_sync_repo_allowlist
        self.repo_denylist = self.config.github_sync_repo_denylist
        self.security_scan_enabled = self.config.github_sync_security_scan_enabled
        self.security_block_severity = self.config.github_sync_security_block_severity

    @classmethod
    def from_env(cls) -> "GitHubOrgSyncer":
        return cls(Citadel.from_env())

    async def status(self) -> dict[str, Any]:
        state = self._load_state()
        return {
            "ok": True,
            "org": self.org,
            "source_url": SOURCE_URL_TEMPLATE.format(org=self.org),
            "dataset": self.config.github_sync_dataset,
            "session_id": self.config.github_sync_session,
            "state_path": str(self.state_path),
            "last_checked_at": state.get("last_checked_at"),
            "last_digest_at": state.get("last_digest_at"),
            "tracked_repositories": len(state.get("repos") or {}),
            "seen_events": len(state.get("seen_event_ids") or []),
            "tracked_commit_repositories": len(state.get("commits") or {}),
            "include_commits": self.include_commits,
            "include_private": self.include_private,
            "repo_allowlist": list(self.repo_allowlist),
            "repo_denylist": list(self.repo_denylist),
            "max_commits_per_repo": self.max_commits_per_repo,
            "max_pull_requests_per_repo": self.max_pull_requests_per_repo,
            "run_improve": self.run_improve,
            "ingest_unchanged": self.ingest_unchanged,
            "security_scan_enabled": self.security_scan_enabled,
            "security_block_severity": self.security_block_severity,
            "last_security_scan": state.get("last_security_scan"),
        }

    async def run(self, *, force: bool = False, dry_run: bool = False) -> dict[str, Any]:
        checked_at = utc_now()
        state = self._load_state()
        repos, events = await asyncio.to_thread(self._fetch_activity)
        previous_repos = state.get("repos") or {}
        previous_event_ids = set(state.get("seen_event_ids") or [])
        changed_repos = [
            repo
            for repo in repos
            if force or previous_repos.get(repo.full_name, {}).get("fingerprint") != repo.fingerprint
        ]
        new_events = [event for event in events if force or event.id not in previous_event_ids]
        commit_candidates = repos if force else changed_repos
        commits_by_repo = await asyncio.to_thread(self._fetch_commits, commit_candidates)
        pull_requests_by_repo = await asyncio.to_thread(self._fetch_pull_requests, repos)
        previous_commits = state.get("commits") or {}
        if not isinstance(previous_commits, dict):
            previous_commits = {}
        seen_commits_by_repo = {
            repo_name: set(shas or [])
            for repo_name, shas in previous_commits.items()
            if isinstance(shas, list)
        }
        new_commits = [
            commit
            for repo_commits in commits_by_repo.values()
            for commit in repo_commits
            if commit.sha and (force or commit.sha not in seen_commits_by_repo.get(commit.repo, set()))
        ]
        window_started_at = self._window_started_at(checked_at)
        recent_pull_requests = [
            pull_request
            for repo_pull_requests in pull_requests_by_repo.values()
            for pull_request in repo_pull_requests
            if self._pull_request_in_window(pull_request, window_started_at)
        ]
        open_pull_requests = [
            pull_request
            for pull_request in recent_pull_requests
            if pull_request.is_open
        ]
        merged_pull_requests = [
            pull_request
            for pull_request in recent_pull_requests
            if pull_request.is_merged
        ]
        active_repositories = _active_repositories(
            changed_repos=changed_repos,
            events=new_events,
            commits=new_commits,
            pull_requests=recent_pull_requests,
        )
        should_ingest = force or self.ingest_unchanged or bool(
            changed_repos or new_events or new_commits or recent_pull_requests
        )
        security_scan = self._scan_activity(
            repos=repos,
            events=new_events,
            commits=new_commits,
            pull_requests=recent_pull_requests,
        )
        security_blocked = bool(security_scan.get("blocked"))
        should_ingest = should_ingest and not security_blocked
        digest = format_digest(
            org=self.org,
            checked_at=checked_at,
            window_started_at=window_started_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
            repos=repos,
            changed_repos=changed_repos,
            events=new_events,
            commits=new_commits,
            open_pull_requests=open_pull_requests,
            merged_pull_requests=merged_pull_requests,
            active_repositories=active_repositories,
            max_commits_per_repo=self.max_commits_per_repo if self.include_commits else None,
        )

        ingest_result = None
        improve_result = None
        if should_ingest and not dry_run:
            ingest_result = await self.citadel.ingest(
                digest,
                dataset=self.config.github_sync_dataset,
                session_id=self.config.github_sync_session,
                tags=["github", self.org, "daily-sync", "repository-activity"],
            )
            if ingest_result.accepted and self.run_improve:
                try:
                    improve_result = await self.citadel.improve(
                        dataset=self.config.github_sync_dataset,
                        session_ids=[self.config.github_sync_session],
                    )
                except Exception as exc:  # pragma: no cover - depends on runtime LLM config.
                    improve_result = {"ok": False, "error": str(exc)}

        if not dry_run:
            tracked_commits = dict(previous_commits)
            for repo_name, repo_commits in commits_by_repo.items():
                tracked_commits[repo_name] = [commit.sha for commit in repo_commits if commit.sha][:500]
            state.update(
                {
                    "version": STATE_VERSION,
                    "org": self.org,
                    "last_checked_at": checked_at,
                    "repos": {repo.full_name: repo.state() for repo in repos},
                    "commits": tracked_commits,
                    "seen_event_ids": [
                        event.id for event in events if event.id
                    ][:500],
                }
            )
            if should_ingest:
                state["last_digest_at"] = checked_at
                state["last_digest"] = digest
            state["last_security_scan"] = {
                "checked_at": checked_at,
                "ok": security_scan.get("ok"),
                "blocked": security_scan.get("blocked"),
                "highest_severity": security_scan.get("highest_severity"),
                "finding_count": security_scan.get("finding_count"),
            }
            self._save_state(state)

        return {
            "ok": True,
            "org": self.org,
            "source_url": SOURCE_URL_TEMPLATE.format(org=self.org),
            "checked_at": checked_at,
            "state_path": str(self.state_path),
            "repos_scanned": len(repos),
            "private_repo_count": len([repo for repo in repos if repo.visibility == "private"]),
            "contains_private_repositories": any(repo.visibility == "private" for repo in repos),
            "window_started_at": window_started_at.isoformat(timespec="seconds").replace(
                "+00:00",
                "Z",
            ),
            "changed_count": len(changed_repos),
            "event_count": len(new_events),
            "commit_count": len(new_commits),
            "open_pull_request_count": len(open_pull_requests),
            "merged_pull_request_count": len(merged_pull_requests),
            "changed_repositories": [repo.summary() for repo in changed_repos[:20]],
            "recent_commits": [commit.summary_dict() for commit in new_commits[:40]],
            "open_pull_requests": [
                pull_request.summary_dict() for pull_request in open_pull_requests[:40]
            ],
            "merged_pull_requests": [
                pull_request.summary_dict() for pull_request in merged_pull_requests[:40]
            ],
            "active_repositories": active_repositories[:20],
            "recent_events": [event.summary_dict() for event in new_events[:20]],
            "ingested": bool(ingest_result and ingest_result.accepted),
            "ingest_reason": (
                "blocked_by_security_scan"
                if security_blocked
                else getattr(ingest_result, "reason", None)
            ),
            "improved": bool(improve_result)
            and not (isinstance(improve_result, dict) and improve_result.get("ok") is False),
            "improve_error": improve_result.get("error")
            if isinstance(improve_result, dict) and improve_result.get("ok") is False
            else None,
            "dry_run": dry_run,
            "digest": digest if dry_run else None,
            "security_scan": security_scan,
        }

    def _fetch_activity(self) -> tuple[list[GitHubRepo], list[GitHubEvent]]:
        repos = self.client.fetch_repos(
            self.org,
            max_repos=self.max_repos,
            include_private=self.include_private,
        )
        repos = [repo for repo in repos if self._repo_allowed(repo)]
        events = self.client.fetch_events(self.org, max_events=self.max_events)
        return repos, events

    def _repo_allowed(self, repo: GitHubRepo) -> bool:
        name = repo.full_name or repo.name
        if not self.include_private and repo.visibility == "private":
            return False
        if self.repo_allowlist and not _matches_any(name, self.repo_allowlist):
            return False
        if self.repo_denylist and _matches_any(name, self.repo_denylist):
            return False
        return True

    def _fetch_commits(self, repos: list[GitHubRepo]) -> dict[str, list[GitHubCommit]]:
        if not self.include_commits or self.max_commits_per_repo <= 0:
            return {}
        commits: dict[str, list[GitHubCommit]] = {}
        for repo in repos:
            if not repo.full_name or repo.archived:
                continue
            commits[repo.full_name] = self.client.fetch_commits(
                repo,
                max_commits=self.max_commits_per_repo,
            )
        return commits

    def _fetch_pull_requests(self, repos: list[GitHubRepo]) -> dict[str, list[GitHubPullRequest]]:
        if self.max_pull_requests_per_repo <= 0:
            return {}
        pull_requests: dict[str, list[GitHubPullRequest]] = {}
        for repo in repos:
            if not repo.full_name or repo.archived:
                continue
            pull_requests[repo.full_name] = self.client.fetch_pull_requests(
                repo,
                max_pull_requests=self.max_pull_requests_per_repo,
            )
        return pull_requests

    def _scan_activity(
        self,
        *,
        repos: list[GitHubRepo],
        events: list[GitHubEvent],
        commits: list[GitHubCommit],
        pull_requests: list[GitHubPullRequest],
    ) -> dict[str, object]:
        if not self.security_scan_enabled:
            return {
                "ok": True,
                "blocked": False,
                "block_severity": self.security_block_severity,
                "highest_severity": None,
                "finding_count": 0,
                "findings": [],
                "enabled": False,
            }
        entries: list[SecurityScanEntry] = []
        for repo in repos:
            entries.append(
                SecurityScanEntry(
                    source="repository",
                    location=repo.full_name,
                    text=" ".join(
                        part
                        for part in (
                            repo.name,
                            repo.full_name,
                            repo.description or "",
                            " ".join(repo.topics),
                            repo.html_url,
                        )
                        if part
                    ),
                )
            )
        for event in events:
            entries.append(
                SecurityScanEntry(
                    source="event",
                    location=f"{event.repo}:{event.id}",
                    text=f"{event.type} {event.actor} {event.summary}",
                )
            )
        for commit in commits:
            entries.append(
                SecurityScanEntry(
                    source="commit",
                    location=f"{commit.repo}@{commit.sha[:12]}",
                    text=" ".join(
                        part
                        for part in (
                            commit.message,
                            commit.html_url,
                            commit.author_login or "",
                            commit.author_name or "",
                        )
                        if part
                    ),
                )
            )
        for pull_request in pull_requests:
            entries.append(
                SecurityScanEntry(
                    source="pull_request",
                    location=f"{pull_request.repo}#{pull_request.number}",
                    text=" ".join(
                        part
                        for part in (
                            pull_request.title,
                            pull_request.html_url,
                            pull_request.user_login or "",
                        )
                        if part
                    ),
                )
            )
        result = scan_text_entries(entries, block_severity=self.security_block_severity)
        result["enabled"] = True
        return result

    def _window_started_at(self, checked_at: str) -> datetime:
        hours = max(1, self.config.organization_digest_window_hours)
        return _parse_github_time(checked_at) - timedelta(hours=hours)

    def _pull_request_in_window(
        self,
        pull_request: GitHubPullRequest,
        window_started_at: datetime,
    ) -> bool:
        timestamps = [pull_request.updated_at, pull_request.created_at]
        if pull_request.is_merged:
            timestamps.insert(0, pull_request.merged_at)
        return any(
            timestamp is not None and _parse_github_time(timestamp) >= window_started_at
            for timestamp in timestamps
        )

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {
                "version": STATE_VERSION,
                "org": self.org,
                "repos": {},
                "commits": {},
                "seen_event_ids": [],
            }
        try:
            with self.state_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return {
                "version": STATE_VERSION,
                "org": self.org,
                "repos": {},
                "commits": {},
                "seen_event_ids": [],
            }
        if not isinstance(data, dict):
            return {
                "version": STATE_VERSION,
                "org": self.org,
                "repos": {},
                "commits": {},
                "seen_event_ids": [],
            }
        data.setdefault("repos", {})
        data.setdefault("commits", {})
        data.setdefault("seen_event_ids", [])
        return data

    def _save_state(self, state: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.state_path.with_suffix(f"{self.state_path.suffix}.tmp")
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(state, file, indent=2, sort_keys=True)
        temp_path.replace(self.state_path)


def format_digest(
    *,
    org: str,
    checked_at: str,
    window_started_at: str | None = None,
    repos: list[GitHubRepo],
    changed_repos: list[GitHubRepo],
    events: list[GitHubEvent],
    commits: list[GitHubCommit],
    open_pull_requests: list[GitHubPullRequest] | None = None,
    merged_pull_requests: list[GitHubPullRequest] | None = None,
    active_repositories: list[dict[str, Any]] | None = None,
    max_commits_per_repo: int | None = None,
) -> str:
    open_pull_requests = open_pull_requests or []
    merged_pull_requests = merged_pull_requests or []
    active_repositories = active_repositories or []
    source_url = SOURCE_URL_TEMPLATE.format(org=org)
    lines = [
        f"# {org} GitHub daily update",
        "",
        f"Checked at: {checked_at}",
        *( [f"Window started at: {window_started_at}"] if window_started_at else [] ),
        f"Source: {source_url}",
        f"Repositories scanned: {len(repos)}",
        f"Changed repositories since last check: {len(changed_repos)}",
        f"New public organization events: {len(events)}",
        f"New commits observed: {len(commits)}",
        f"Open pull requests active in window: {len(open_pull_requests)}",
        f"Merged pull requests in window: {len(merged_pull_requests)}",
        "",
        "## Changed repositories",
    ]

    if changed_repos:
        for repo in changed_repos[:20]:
            topics = f" Topics: {', '.join(repo.topics[:8])}." if repo.topics else ""
            description = _short(repo.description) or "No description."
            lines.append(
                "- "
                f"{repo.full_name} ({repo.language or 'unknown language'}): "
                f"pushed {repo.pushed_at or 'unknown'}, updated {repo.updated_at or 'unknown'}, "
                f"open issues {repo.open_issues_count}, stars {repo.stargazers_count}, "
                f"forks {repo.forks_count}. {description}{topics} {repo.html_url}"
            )
    else:
        lines.append("- No repository metadata changed since the last check.")

    lines.extend(["", "## Open pull requests worth attention"])
    if open_pull_requests:
        for pull_request in open_pull_requests[:20]:
            author = f" by {pull_request.user_login}" if pull_request.user_login else ""
            draft = " draft" if pull_request.draft else ""
            lines.append(
                "- "
                f"{pull_request.repo}#{pull_request.number}{author}{draft}: "
                f"{pull_request.title}. Updated {pull_request.updated_at or 'unknown'}. "
                f"{pull_request.html_url}"
            )
    else:
        lines.append("- No open pull requests were active in the window.")

    lines.extend(["", "## Merged pull requests"])
    if merged_pull_requests:
        for pull_request in merged_pull_requests[:20]:
            author = f" by {pull_request.user_login}" if pull_request.user_login else ""
            lines.append(
                "- "
                f"{pull_request.repo}#{pull_request.number}{author}: "
                f"{pull_request.title}. Merged {pull_request.merged_at or 'unknown'}. "
                f"{pull_request.html_url}"
            )
    else:
        lines.append("- No pull requests were merged in the window.")

    lines.extend(["", "## Recent public activity"])
    if events:
        for event in events[:25]:
            lines.append(
                "- "
                f"{event.created_at}: {event.actor} on {event.repo}: "
                f"{event.type} - {event.summary}"
            )
    else:
        lines.append("- No new public org events were returned by GitHub.")

    lines.extend(["", "## Recent commits"])
    if max_commits_per_repo:
        lines.append(
            f"Showing up to {max_commits_per_repo} most recent commit(s) per changed "
            "repository; repositories with more commits than this are truncated here."
        )
    if commits:
        for commit in commits[:40]:
            author = commit.author_login or commit.author_name or "unknown author"
            lines.append(
                "- "
                f"{commit.authored_at or 'unknown time'}: {author} committed "
                f"{commit.sha[:12]} to {commit.repo}: {commit.message}. {commit.html_url}"
            )
    else:
        lines.append("- No new commits were observed in changed repositories.")

    lines.extend(["", "## Most recently pushed repositories"])
    for repo in repos[:10]:
        lines.append(
            "- "
            f"{repo.full_name}: pushed {repo.pushed_at or 'unknown'}; "
            f"language {repo.language or 'unknown'}; issues {repo.open_issues_count}; "
            f"{repo.html_url}"
        )

    lines.extend(["", "## Repository momentum"])
    if active_repositories:
        for repository in active_repositories[:10]:
            lines.append(
                "- "
                f"{repository['repo']}: activity score {repository['score']} "
                f"(repos {repository['changed_repos']}, PRs {repository['pull_requests']}, "
                f"commits {repository['commits']}, events {repository['events']})"
            )
    else:
        lines.append("- No active repositories were identified from the source packet.")

    return "\n".join(lines).strip()


def _parse_github_time(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    return datetime.fromisoformat(text).astimezone(UTC)


def _active_repositories(
    *,
    changed_repos: list[GitHubRepo],
    events: list[GitHubEvent],
    commits: list[GitHubCommit],
    pull_requests: list[GitHubPullRequest],
) -> list[dict[str, Any]]:
    activity: dict[str, dict[str, Any]] = {}

    def entry(repo: str) -> dict[str, Any]:
        return activity.setdefault(
            repo,
            {
                "repo": repo,
                "score": 0,
                "changed_repos": 0,
                "pull_requests": 0,
                "commits": 0,
                "events": 0,
            },
        )

    for repo in changed_repos:
        row = entry(repo.full_name)
        row["changed_repos"] += 1
        row["score"] += 1
    for event in events:
        row = entry(event.repo)
        row["events"] += 1
        row["score"] += 1
    for commit in commits:
        row = entry(commit.repo)
        row["commits"] += 1
        row["score"] += 2
    for pull_request in pull_requests:
        row = entry(pull_request.repo)
        row["pull_requests"] += 1
        row["score"] += 3

    return sorted(
        activity.values(),
        key=lambda row: (row["score"], row["pull_requests"], row["commits"], row["events"]),
        reverse=True,
    )


def _event_summary(event_type: str, payload: dict[str, Any]) -> str:
    if event_type == "PushEvent":
        commits = payload.get("commits") or []
        # GitHub's events feed reports the full push size separately from the
        # (possibly truncated) inline commit array. Prefer the real count so the
        # digest never claims "Pushed 0 commit(s)" when commits exist.
        count = payload.get("size")
        if count is None:
            count = payload.get("distinct_size")
        if count is None:
            count = len(commits)
        messages = [_short(commit.get("message"), length=80) for commit in commits[:2]]
        ref = str(payload.get("ref") or "").removeprefix("refs/heads/")
        detail = "; ".join(message for message in messages if message)
        plural = "" if count == 1 else "s"
        return f"Pushed {count} commit{plural} to {ref or 'a branch'}" + (
            f": {detail}" if detail else ""
        )
    if event_type == "PullRequestEvent":
        pull_request = payload.get("pull_request") or {}
        action = payload.get("action", "updated")
        if action == "closed" and pull_request.get("merged"):
            action = "merged"
        title = _short(pull_request.get("title"), length=100) or "(no title)"
        return f"{action} pull request #{pull_request.get('number')}: {title}"
    if event_type == "PullRequestReviewEvent":
        pull_request = payload.get("pull_request") or {}
        review = payload.get("review") or {}
        title = _short(pull_request.get("title"), length=100) or "(no title)"
        return (
            f"{payload.get('action', 'reviewed')} review "
            f"{review.get('state', 'submitted')} on pull request "
            f"#{pull_request.get('number')}: {title}"
        )
    if event_type == "PullRequestReviewCommentEvent":
        pull_request = payload.get("pull_request") or {}
        comment = payload.get("comment") or {}
        body = _short(comment.get("body"), length=100) or "(no comment body)"
        return (
            f"{payload.get('action', 'commented')} review comment on pull request "
            f"#{pull_request.get('number')}: {body}"
        )
    if event_type == "IssuesEvent":
        issue = payload.get("issue") or {}
        title = _short(issue.get("title"), length=100) or "(no title)"
        return f"{payload.get('action', 'updated')} issue #{issue.get('number')}: {title}"
    if event_type == "CreateEvent":
        return f"Created {payload.get('ref_type', 'ref')} {payload.get('ref') or ''}".strip()
    if event_type == "ReleaseEvent":
        release = payload.get("release") or {}
        name = _short(release.get("name"), length=100) or release.get("tag_name") or "(unnamed)"
        return f"{payload.get('action', 'updated')} release {name}"
    if event_type == "ForkEvent":
        forkee = payload.get("forkee") or {}
        return f"Forked to {forkee.get('full_name', 'a new repository')}"
    if event_type == "WatchEvent":
        return f"{payload.get('action', 'starred')} repository"
    return _short(event_type.replace("Event", " event"))


async def _sync_github(args: argparse.Namespace) -> None:
    syncer = GitHubOrgSyncer(
        Citadel.from_env(),
        org=args.org,
        state_path=args.state_path,
        max_repos=args.max_repos,
        max_events=args.max_events,
        max_commits_per_repo=args.max_commits_per_repo,
        include_commits=not args.skip_commits,
        ingest_unchanged=not args.skip_unchanged,
        run_improve=not args.skip_improve,
    )
    result = await syncer.run(force=args.force, dry_run=args.dry_run)
    print(json.dumps(result, indent=2, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m kb.github_sync")
    parser.add_argument("--org", default=None, help="GitHub organization login")
    parser.add_argument("--state-path", default=None, help="Persistent sync state JSON path")
    parser.add_argument("--max-repos", type=int, default=None, help="Maximum repositories to scan")
    parser.add_argument("--max-events", type=int, default=None, help="Maximum org events to scan")
    parser.add_argument(
        "--max-commits-per-repo",
        type=int,
        default=None,
        help="Maximum recent commits to summarize per changed repository",
    )
    parser.add_argument("--force", action="store_true", help="Treat all fetched activity as new")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and print without ingesting")
    parser.add_argument("--skip-improve", action="store_true", help="Do not run Citadel improve")
    parser.add_argument("--skip-commits", action="store_true", help="Do not fetch commit summaries")
    parser.add_argument(
        "--skip-unchanged",
        action="store_true",
        help="Skip ingest when GitHub reports no new activity",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(_sync_github(args))


if __name__ == "__main__":
    main()
