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
ROLE_ORDER = {"reader": 1, "writer": 2, "admin": 3}

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


def session_token(role: str, access_key: str) -> str:
    message = f"citadel-session:v2:{role}".encode("utf-8")
    return hmac.new(access_key.encode("utf-8"), message, hashlib.sha256).hexdigest()


def cookie_value(role: str, access_key: str) -> str:
    return f"{role}:{session_token(role, access_key)}"


def role_for_access_key(access_key: str) -> str | None:
    for role, key in configured_access_keys():
        if secrets.compare_digest(access_key, key):
            return role
    return None


def session_role(request: Request) -> str | None:
    session = request.cookies.get(ADMIN_COOKIE)
    if not session:
        return None
    for role, key in configured_access_keys():
        if secrets.compare_digest(session, cookie_value(role, key)):
            return role
    return None


def require_role(request: Request, minimum_role: str) -> str:
    role = session_role(request)
    if not role:
        raise HTTPException(status_code=401, detail="Access key required.")
    if ROLE_ORDER[role] < ROLE_ORDER[minimum_role]:
        raise HTTPException(status_code=403, detail=f"{minimum_role.title()} access required.")
    return role


def role_payload(role: str) -> dict[str, Any]:
    return {
        "role": role,
        "capabilities": {
            "read": ROLE_ORDER[role] >= ROLE_ORDER["reader"],
            "write": ROLE_ORDER[role] >= ROLE_ORDER["writer"],
            "admin": ROLE_ORDER[role] >= ROLE_ORDER["admin"],
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
    if not configured_access_keys():
        raise HTTPException(status_code=503, detail="Access keys are not configured.")
    if not access_key:
        raise HTTPException(status_code=422, detail="Access key is required.")
    role = role_for_access_key(access_key)
    if not role:
        raise HTTPException(status_code=401, detail="Access key was rejected.")
    response.set_cookie(
        ADMIN_COOKIE,
        cookie_value(role, access_key),
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=60 * 60 * 12,
    )
    return {"ok": True, **role_payload(role)}


@app.post("/admin/logout")
async def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(ADMIN_COOKIE)
    return {"ok": True}


@app.get("/api/session")
async def current_session(request: Request) -> dict[str, Any]:
    role = require_role(request, "reader")
    return {"ok": True, **role_payload(role)}


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
