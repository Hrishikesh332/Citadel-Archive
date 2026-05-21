from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from pathlib import Path
import secrets
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from kb.access import AccessIdentity, AccessStore, ROLE_ORDER, hash_api_token
from kb.github_sync import GitHubOrgSyncer
from kb.mesh import MeshState
from kb.models import FeedbackRequest
from kb.service import Citadel

app = FastAPI(
    title="Citadel Archive",
    version="0.1.0",
    description="Self-hosted knowledge-base wrapper around Cognee.",
)
STATIC_DIR = Path(__file__).with_name("static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
ADMIN_COOKIE = "citadel_admin"

LOGIN_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Citadel Admin</title>
    <link rel="stylesheet" href="/static/styles.css" />
  </head>
  <body>
    <main class="login-shell">
      <section class="login-panel">
        <div class="brand compact">
          <div class="brand-mark" aria-hidden="true">CA</div>
          <div>
            <h1>Citadel Archive</h1>
            <p>Workspace access</p>
          </div>
        </div>
        <form id="loginForm" class="form">
          <div class="field">
            <label for="adminKey">Access key</label>
            <input
              id="adminKey"
              name="accessKey"
              type="password"
              autocomplete="current-password"
              required
              autofocus
            />
          </div>
          <p id="loginError" class="form-error" role="alert"></p>
          <button id="loginSubmit" class="primary-button" type="submit">Open workspace</button>
        </form>
      </section>
    </main>
    <script>
      const form = document.getElementById("loginForm");
      const error = document.getElementById("loginError");
      const button = document.getElementById("loginSubmit");
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        error.textContent = "";
        button.disabled = true;
        button.setAttribute("aria-busy", "true");
        button.textContent = "Checking";
        const access_key = new FormData(form).get("accessKey");
        try {
          const response = await fetch("/admin/session", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ access_key }),
          });
          if (!response.ok) {
            const body = await response.json().catch(() => ({}));
            throw new Error(body.detail || "Admin key was rejected.");
          }
          window.location.assign("/");
        } catch (err) {
          error.textContent = err.message;
        } finally {
          button.disabled = false;
          button.setAttribute("aria-busy", "false");
          button.textContent = "Open workspace";
        }
      });
    </script>
  </body>
</html>
"""


class IngestBody(BaseModel):
    data: str = Field(min_length=1)
    dataset: str | None = None
    tags: list[str] = Field(default_factory=list)
    session_id: str | None = None


class SearchBody(BaseModel):
    query: str = Field(min_length=1)
    dataset: str | None = None
    session_id: str | None = None
    top_k: int = Field(default=10, ge=1, le=100)


class FeedbackBody(BaseModel):
    qa_id: str = Field(min_length=1)
    score: int | None = Field(default=None, ge=-1, le=1)
    text: str | None = None
    session_id: str | None = None
    dataset: str | None = None


class ImproveBody(BaseModel):
    dataset: str | None = None
    session_ids: list[str] | None = None


class AdminSessionBody(BaseModel):
    access_key: str | None = Field(default=None, min_length=1)
    admin_key: str | None = Field(default=None, min_length=1)


class GitHubSyncBody(BaseModel):
    force: bool = False


class AccessTokenBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role: str = Field(default="reader")
    kind: str = Field(default="service_account")
    scopes: list[str] | None = None
    team_id: str | None = None
    expires_at: str | None = None


def get_citadel() -> Citadel:
    if not hasattr(app.state, "citadel"):
        app.state.citadel = Citadel.from_env()
    return app.state.citadel


def get_mesh() -> MeshState:
    if not hasattr(app.state, "mesh"):
        app.state.mesh = MeshState()
    return app.state.mesh


def get_github_syncer() -> GitHubOrgSyncer:
    if hasattr(app.state, "github_syncer"):
        return app.state.github_syncer
    return GitHubOrgSyncer(get_citadel())


def get_access_store() -> AccessStore:
    existing = getattr(app.state, "access_store", None)
    if isinstance(existing, AccessStore):
        return existing
    config = get_citadel().config
    app.state.access_store = AccessStore(
        config.access_store_path,
        max_audit_events=config.audit_max_events,
    )
    return app.state.access_store


def sse(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def configured_access_keys() -> list[tuple[str, str]]:
    config = get_citadel().config
    entries: list[tuple[str, str]] = []
    if config.admin_key:
        entries.append(("admin", config.admin_key))
    entries.extend(("writer", key) for key in config.writer_keys)
    entries.extend(("reader", key) for key in config.reader_keys)
    return entries


def env_identity(role: str) -> AccessIdentity:
    return AccessIdentity(
        role=role,
        actor_id=f"bootstrap:{role}",
        actor_kind="bootstrap_key",
        actor_name=f"{role.title()} bootstrap key",
        source="env",
        scopes=(),
    )


def session_token(role: str, access_key: str) -> str:
    message = f"citadel-session:v2:{role}".encode("utf-8")
    return hmac.new(access_key.encode("utf-8"), message, hashlib.sha256).hexdigest()


def cookie_value(role: str, access_key: str) -> str:
    return f"{role}:{session_token(role, access_key)}"


def token_session_signature(role: str, token_id: str, token_hash: str) -> str:
    message = f"citadel-session:v2:token:{role}:{token_id}".encode("utf-8")
    return hmac.new(token_hash.encode("utf-8"), message, hashlib.sha256).hexdigest()


def token_cookie_value(identity: AccessIdentity, token_hash: str) -> str:
    if not identity.token_id:
        raise ValueError("Token identity missing token ID.")
    signature = token_session_signature(identity.role, identity.token_id, token_hash)
    return f"token:{identity.role}:{identity.token_id}:{signature}"


def access_key_identity(access_key: str) -> tuple[AccessIdentity, str] | None:
    for role, key in configured_access_keys():
        if secrets.compare_digest(access_key, key):
            return env_identity(role), cookie_value(role, access_key)
    token_session = get_access_store().authenticate_token(access_key)
    if token_session:
        return token_session.identity, token_cookie_value(
            token_session.identity,
            hash_api_token(access_key),
        )
    return None


def session_identity(request: Request) -> AccessIdentity | None:
    session = request.cookies.get(ADMIN_COOKIE)
    if not session:
        return None
    for role, key in configured_access_keys():
        if secrets.compare_digest(session, cookie_value(role, key)):
            return env_identity(role)
    parts = session.split(":")
    if len(parts) != 4 or parts[0] != "token":
        return None
    _, role, token_id, signature = parts
    token_session = get_access_store().token_session(token_id)
    if not token_session or token_session.identity.role != role:
        return None
    expected = token_session_signature(role, token_id, token_session.token_hash)
    if not secrets.compare_digest(signature, expected):
        return None
    return token_session.identity


def session_role(request: Request) -> str | None:
    identity = session_identity(request)
    return identity.role if identity else None


def require_role(request: Request, minimum_role: str) -> AccessIdentity:
    identity = session_identity(request)
    if not identity:
        raise HTTPException(status_code=401, detail="Access key required.")
    if ROLE_ORDER[identity.role] < ROLE_ORDER[minimum_role]:
        raise HTTPException(status_code=403, detail=f"{minimum_role.title()} access required.")
    return identity


def role_payload(role: str, identity: AccessIdentity | None = None) -> dict[str, Any]:
    return {
        "role": role,
        "capabilities": {
            "read": ROLE_ORDER[role] >= ROLE_ORDER["reader"],
            "write": ROLE_ORDER[role] >= ROLE_ORDER["writer"],
            "admin": ROLE_ORDER[role] >= ROLE_ORDER["admin"],
        },
        "actor": None
        if identity is None
        else {
            "id": identity.actor_id,
            "kind": identity.actor_kind,
            "name": identity.actor_name,
            "source": identity.source,
            "token_id": identity.token_id,
            "scopes": list(identity.scopes),
        },
    }


@app.get("/", include_in_schema=False)
async def ui(request: Request) -> Response:
    if not session_role(request):
        return RedirectResponse("/login", status_code=303)
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/login", include_in_schema=False)
async def login() -> HTMLResponse:
    return HTMLResponse(LOGIN_HTML)


@app.post("/admin/session")
async def create_admin_session(body: AdminSessionBody, response: Response) -> dict[str, Any]:
    access_key = body.access_key or body.admin_key
    if not configured_access_keys() and not get_access_store().has_tokens():
        raise HTTPException(status_code=503, detail="Access keys are not configured.")
    if not access_key:
        raise HTTPException(status_code=422, detail="Access key is required.")
    identity_with_cookie = access_key_identity(access_key)
    if not identity_with_cookie:
        raise HTTPException(status_code=401, detail="Access key was rejected.")
    identity, session_cookie = identity_with_cookie
    response.set_cookie(
        ADMIN_COOKIE,
        session_cookie,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=60 * 60 * 12,
    )
    return {"ok": True, **role_payload(identity.role, identity)}


@app.post("/admin/logout")
async def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(ADMIN_COOKIE)
    return {"ok": True}


@app.get("/api/session")
async def current_session(request: Request) -> dict[str, Any]:
    identity = require_role(request, "reader")
    return {"ok": True, **role_payload(identity.role, identity)}


@app.get("/api/access")
async def access_snapshot(request: Request) -> dict[str, Any]:
    require_role(request, "admin")
    bootstrap_counts = {"reader": 0, "writer": 0, "admin": 0}
    for role, _ in configured_access_keys():
        bootstrap_counts[role] += 1
    return {
        "ok": True,
        "bootstrap_keys": bootstrap_counts,
        **get_access_store().snapshot(),
    }


@app.get("/api/audit")
async def audit_snapshot(request: Request) -> dict[str, Any]:
    require_role(request, "admin")
    return {"ok": True, "audit_events": get_access_store().snapshot()["audit_events"]}


@app.post("/api/access/tokens")
async def create_access_token(body: AccessTokenBody, request: Request) -> dict[str, Any]:
    actor = require_role(request, "admin")
    try:
        created = get_access_store().create_principal_token(
            name=body.name,
            kind=body.kind,
            role=body.role,
            scopes=body.scopes,
            team_id=body.team_id,
            expires_at=body.expires_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    get_access_store().record_event(
        action="access.token.create",
        actor=actor,
        success=True,
        detail={
            "principal_id": created.principal.id,
            "token_id": created.api_token.id,
            "role": created.api_token.role,
            "kind": created.principal.kind,
        },
    )
    return {
        "ok": True,
        "token": created.token,
        "principal": jsonable_encoder(created.principal),
        "api_token": jsonable_encoder(
            {key: value for key, value in created.api_token.__dict__.items() if key != "token_hash"}
        ),
    }


@app.post("/api/access/tokens/{token_id}/revoke")
async def revoke_access_token(token_id: str, request: Request) -> dict[str, Any]:
    actor = require_role(request, "admin")
    revoked = get_access_store().revoke_token(token_id)
    if not revoked:
        get_access_store().record_event(
            action="access.token.revoke",
            actor=actor,
            success=False,
            detail={"token_id": token_id, "reason": "not_found"},
        )
        raise HTTPException(status_code=404, detail="Token not found.")
    get_access_store().record_event(
        action="access.token.revoke",
        actor=actor,
        success=True,
        detail={"token_id": token_id},
    )
    redacted = {key: value for key, value in revoked.__dict__.items() if key != "token_hash"}
    return {"ok": True, "api_token": jsonable_encoder(redacted)}


@app.get("/healthz")
async def healthz() -> dict[str, str | bool]:
    return {"ok": True, "service": "citadel"}


@app.get("/readyz")
async def readyz(request: Request) -> dict[str, Any]:
    require_role(request, "reader")
    config = get_citadel().config
    return {
        "ok": True,
        "service": "citadel",
        "tenant_id": config.tenant_id,
        "default_dataset": config.default_dataset,
        "auto_improve": config.auto_improve,
        "build_global_context_index": config.build_global_context_index,
    }


@app.get("/api/mesh")
async def mesh(request: Request) -> Any:
    require_role(request, "reader")
    citadel = get_citadel()
    return jsonable_encoder(await get_mesh().snapshot(citadel.config))


@app.get("/api/indexes")
async def indexes(request: Request) -> Any:
    require_role(request, "reader")
    citadel = get_citadel()
    snapshot = await get_mesh().snapshot(citadel.config)
    return jsonable_encoder({"indexes": snapshot["indexes"], "stats": snapshot["stats"]})


@app.get("/api/github-sync")
async def github_sync_status(request: Request) -> Any:
    require_role(request, "reader")
    return jsonable_encoder(await get_github_syncer().status())


@app.post("/api/github-sync/run")
async def run_github_sync(body: GitHubSyncBody, request: Request) -> Any:
    require_role(request, "admin")
    citadel = get_citadel()
    mesh_state = get_mesh()
    try:
        result = await get_github_syncer().run(force=body.force)
    except Exception as exc:  # pragma: no cover - depends on GitHub and runtime Cognee config.
        await mesh_state.record_error(citadel.config, operation="github_sync", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    await mesh_state.record_github_sync(citadel.config, result)
    return jsonable_encoder(result)


@app.get("/events")
async def events(request: Request) -> StreamingResponse:
    require_role(request, "reader")
    mesh_state = get_mesh()
    queue = mesh_state.subscribe()

    async def stream() -> Any:
        try:
            snapshot = await mesh_state.snapshot(get_citadel().config)
            yield sse("snapshot", snapshot)
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield ": ping\n\n"
                    continue
                yield sse("mesh-event", event)
        finally:
            mesh_state.unsubscribe(queue)

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/ingest")
async def ingest(body: IngestBody, request: Request) -> Any:
    require_role(request, "writer")
    citadel = get_citadel()
    mesh_state = get_mesh()
    dataset = body.dataset or citadel.config.default_dataset
    try:
        result = await citadel.ingest(
            body.data,
            dataset=body.dataset,
            tags=body.tags,
            session_id=body.session_id,
        )
    except Exception as exc:  # pragma: no cover - depends on runtime Cognee configuration.
        await mesh_state.record_error(citadel.config, operation="ingest", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    await mesh_state.record_ingest(
        citadel.config,
        result,
        data=body.data,
        dataset=dataset,
        tags=body.tags,
    )
    return jsonable_encoder(result)


@app.post("/search")
async def search(body: SearchBody, request: Request) -> Any:
    require_role(request, "reader")
    citadel = get_citadel()
    mesh_state = get_mesh()
    dataset = body.dataset or citadel.config.default_dataset
    try:
        results = await citadel.search(
            body.query,
            dataset=body.dataset,
            session_id=body.session_id,
            top_k=body.top_k,
        )
    except Exception as exc:  # pragma: no cover - depends on runtime Cognee configuration.
        await mesh_state.record_error(citadel.config, operation="search", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    await mesh_state.record_search(
        citadel.config,
        query=body.query,
        dataset=dataset,
        result_count=len(results),
    )
    return jsonable_encoder({"results": results})


@app.post("/feedback")
async def feedback(body: FeedbackBody, request: Request) -> Any:
    require_role(request, "writer")
    citadel = get_citadel()
    mesh_state = get_mesh()
    dataset = body.dataset or citadel.config.default_dataset
    try:
        result = await citadel.feedback(
            FeedbackRequest(
                qa_id=body.qa_id,
                score=body.score,
                text=body.text,
                session_id=body.session_id,
                dataset=body.dataset,
            )
        )
    except Exception as exc:  # pragma: no cover - depends on runtime Cognee configuration.
        await mesh_state.record_error(citadel.config, operation="feedback", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    await mesh_state.record_feedback(
        citadel.config,
        qa_id=body.qa_id,
        dataset=dataset,
        result=result,
    )
    return jsonable_encoder(result)


@app.post("/improve")
async def improve(body: ImproveBody, request: Request) -> Any:
    require_role(request, "admin")
    return await run_improve(body)


@app.post("/api/self-upgrade")
async def self_upgrade(body: ImproveBody, request: Request) -> Any:
    require_role(request, "admin")
    return await run_improve(body)


async def run_improve(body: ImproveBody) -> Any:
    citadel = get_citadel()
    mesh_state = get_mesh()
    dataset = body.dataset or citadel.config.default_dataset
    try:
        result = await citadel.improve(
            dataset=body.dataset,
            session_ids=body.session_ids,
        )
    except Exception as exc:  # pragma: no cover - depends on runtime Cognee configuration.
        await mesh_state.record_error(citadel.config, operation="improve", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    await mesh_state.record_upgrade(
        citadel.config,
        dataset=dataset,
        session_ids=body.session_ids,
    )
    return jsonable_encoder({"result": result})
