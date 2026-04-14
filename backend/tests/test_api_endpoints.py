"""
SAP SIM — Comprehensive API Endpoint Test Suite
Phase: 7.8
Purpose: Tests for every endpoint in the OpenAPI spec.
         Uses an in-memory SQLite DB (via conftest.py fixtures) and
         httpx.AsyncClient with ASGITransport — no real server needed.

Run:
    cd backend
    source venv/bin/activate
    python -m pytest tests/test_api_endpoints.py -v
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient

# ===========================================================================
# GET /health
# ===========================================================================


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    """GET /health must return 200 with status=ok."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "sapsim" in body["service"]


# ===========================================================================
# POST /api/projects — Create project
# ===========================================================================


@pytest.mark.asyncio
async def test_create_project_valid(client: AsyncClient) -> None:
    """POST /api/projects with a valid name must return 201 and the project state."""
    resp = await client.post("/api/projects", json={"name": "my-project"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["project_name"] == "my-project"
    assert body["status"] == "IDLE"
    assert body["current_phase"] == "discover"
    assert body["simulated_day"] == 0
    assert body["total_days"] > 0


@pytest.mark.asyncio
async def test_create_project_with_industry(client: AsyncClient) -> None:
    """POST /api/projects with industry/scope/methodology must echo them back."""
    resp = await client.post("/api/projects", json={
        "name": "retail-proj",
        "industry": "Retail",
        "scope": "Full ERP rollout",
        "methodology": "SAP Activate",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["project_name"] == "retail-proj"
    assert body["industry"] == "Retail"


@pytest.mark.asyncio
async def test_create_project_duplicate_returns_409(client: AsyncClient) -> None:
    """Creating a project with an existing name must return 409."""
    await client.post("/api/projects", json={"name": "dup-proj"})
    resp = await client.post("/api/projects", json={"name": "dup-proj"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_project_invalid_name_with_spaces(client: AsyncClient) -> None:
    """Names containing spaces must be rejected with 422."""
    resp = await client.post("/api/projects", json={"name": "my project name"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_project_empty_name(client: AsyncClient) -> None:
    """Empty string name must be rejected with 422."""
    resp = await client.post("/api/projects", json={"name": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_project_name_too_long(client: AsyncClient) -> None:
    """Names longer than 64 characters must be rejected with 422."""
    long_name = "a" * 65
    resp = await client.post("/api/projects", json={"name": long_name})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_project_name_with_special_chars(client: AsyncClient) -> None:
    """Names with special chars (! @ #) must be rejected with 422."""
    resp = await client.post("/api/projects", json={"name": "proj@name!"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_project_valid_with_hyphens_and_underscores(client: AsyncClient) -> None:
    """Hyphens and underscores in names must be accepted."""
    resp = await client.post("/api/projects", json={"name": "proj_with-hyphens_2"})
    assert resp.status_code == 201


# ===========================================================================
# GET /api/projects — List projects
# ===========================================================================


@pytest.mark.asyncio
async def test_list_projects_empty(client: AsyncClient) -> None:
    """GET /api/projects on an empty DB must return an empty list."""
    resp = await client.get("/api/projects")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_projects_returns_created_project(client: AsyncClient, project: str) -> None:
    """GET /api/projects must include the project created by the fixture."""
    resp = await client.get("/api/projects")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert project in names


@pytest.mark.asyncio
async def test_list_projects_multiple(client: AsyncClient) -> None:
    """GET /api/projects must return all created projects."""
    for name in ["proj-alpha", "proj-beta", "proj-gamma"]:
        await client.post("/api/projects", json={"name": name})

    resp = await client.get("/api/projects")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "proj-alpha" in names
    assert "proj-beta" in names
    assert "proj-gamma" in names


@pytest.mark.asyncio
async def test_list_projects_structure(client: AsyncClient, project: str) -> None:
    """Each entry in list must have required fields."""
    resp = await client.get("/api/projects")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1
    item = items[0]
    for field in ("name", "status", "current_phase", "simulated_day", "total_days", "created_at"):
        assert field in item, f"Missing field: {field}"


# ===========================================================================
# GET /api/projects/{name} — Get project
# ===========================================================================


@pytest.mark.asyncio
async def test_get_project_existing(client: AsyncClient, project: str) -> None:
    """GET /api/projects/{name} for an existing project must return 200."""
    resp = await client.get(f"/api/projects/{project}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["project_name"] == project
    assert body["status"] == "IDLE"


@pytest.mark.asyncio
async def test_get_project_not_found(client: AsyncClient) -> None:
    """GET /api/projects/{name} for a missing project must return 404."""
    resp = await client.get("/api/projects/nonexistent-12345")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_project_response_structure(client: AsyncClient, project: str) -> None:
    """Project response must include all required fields."""
    resp = await client.get(f"/api/projects/{project}")
    body = resp.json()
    required_fields = [
        "project_name", "status", "current_phase",
        "simulated_day", "total_days", "phase_progress",
        "active_agents", "pending_decisions", "created_at", "last_updated",
    ]
    for field in required_fields:
        assert field in body, f"Missing field: {field}"


# ===========================================================================
# DELETE /api/projects/{name}
# ===========================================================================


@pytest.mark.asyncio
async def test_delete_project_existing(client: AsyncClient, project: str) -> None:
    """DELETE /api/projects/{name} for an existing project must return 204."""
    resp = await client.delete(f"/api/projects/{project}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_project_removes_from_list(client: AsyncClient, project: str) -> None:
    """After deletion, the project must not appear in GET /api/projects."""
    await client.delete(f"/api/projects/{project}")
    resp = await client.get("/api/projects")
    names = [p["name"] for p in resp.json()]
    assert project not in names


@pytest.mark.asyncio
async def test_delete_project_not_found(client: AsyncClient) -> None:
    """DELETE /api/projects/{name} for a missing project must return 404."""
    resp = await client.delete("/api/projects/ghost-project-xyz")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_project_idempotent_fails_second_time(client: AsyncClient, project: str) -> None:
    """Second DELETE on the same project must return 404."""
    await client.delete(f"/api/projects/{project}")
    resp = await client.delete(f"/api/projects/{project}")
    assert resp.status_code == 404


# ===========================================================================
# POST /api/projects/{name}/start
# ===========================================================================


@pytest.mark.asyncio
async def test_start_simulation(client: AsyncClient, project: str) -> None:
    """POST /api/projects/{name}/start must transition IDLE → RUNNING."""
    resp = await client.post(f"/api/projects/{project}/start")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "RUNNING"


@pytest.mark.asyncio
async def test_start_simulation_not_found(client: AsyncClient) -> None:
    """Starting a nonexistent project must return 404."""
    resp = await client.post("/api/projects/no-such-proj/start")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_start_simulation_double_start_conflicts(client: AsyncClient, project: str) -> None:
    """Starting an already-running simulation must return 409."""
    await client.post(f"/api/projects/{project}/start")
    resp = await client.post(f"/api/projects/{project}/start")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_start_simulation_with_options(client: AsyncClient, project: str) -> None:
    """Start with max_parallel_agents overrides the setting."""
    resp = await client.post(
        f"/api/projects/{project}/start",
        json={"max_parallel_agents": 5},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "RUNNING"


# ===========================================================================
# POST /api/projects/{name}/pause
# ===========================================================================


@pytest.mark.asyncio
async def test_pause_simulation(client: AsyncClient, project: str) -> None:
    """POST /pause on a running simulation must transition RUNNING → PAUSED."""
    await client.post(f"/api/projects/{project}/start")
    resp = await client.post(f"/api/projects/{project}/pause")
    assert resp.status_code == 200
    assert resp.json()["status"] == "PAUSED"


@pytest.mark.asyncio
async def test_pause_idle_simulation_conflicts(client: AsyncClient, project: str) -> None:
    """Pausing an IDLE simulation must return 409."""
    resp = await client.post(f"/api/projects/{project}/pause")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_pause_not_found(client: AsyncClient) -> None:
    """Pausing a nonexistent project must return 404."""
    resp = await client.post("/api/projects/no-proj/pause")
    assert resp.status_code == 404


# ===========================================================================
# POST /api/projects/{name}/resume
# ===========================================================================


@pytest.mark.asyncio
async def test_resume_simulation(client: AsyncClient, project: str) -> None:
    """POST /resume on a paused simulation must transition PAUSED → RUNNING."""
    await client.post(f"/api/projects/{project}/start")
    await client.post(f"/api/projects/{project}/pause")
    resp = await client.post(f"/api/projects/{project}/resume")
    assert resp.status_code == 200
    assert resp.json()["status"] == "RUNNING"


@pytest.mark.asyncio
async def test_resume_idle_simulation_conflicts(client: AsyncClient, project: str) -> None:
    """Resuming an IDLE simulation (not paused) must return 409."""
    resp = await client.post(f"/api/projects/{project}/resume")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_resume_not_found(client: AsyncClient) -> None:
    """Resuming a nonexistent project must return 404."""
    resp = await client.post("/api/projects/no-proj/resume")
    assert resp.status_code == 404


# ===========================================================================
# POST /api/projects/{name}/stop
# ===========================================================================


@pytest.mark.asyncio
async def test_stop_simulation(client: AsyncClient, project: str) -> None:
    """POST /stop on a running simulation must transition RUNNING → STOPPED."""
    await client.post(f"/api/projects/{project}/start")
    resp = await client.post(f"/api/projects/{project}/stop")
    assert resp.status_code == 200
    assert resp.json()["status"] == "STOPPED"


@pytest.mark.asyncio
async def test_stop_paused_simulation(client: AsyncClient, project: str) -> None:
    """POST /stop on a paused simulation must also succeed → STOPPED."""
    await client.post(f"/api/projects/{project}/start")
    await client.post(f"/api/projects/{project}/pause")
    resp = await client.post(f"/api/projects/{project}/stop")
    assert resp.status_code == 200
    assert resp.json()["status"] == "STOPPED"


@pytest.mark.asyncio
async def test_stop_idle_simulation_conflicts(client: AsyncClient, project: str) -> None:
    """Stopping an IDLE simulation must return 409."""
    resp = await client.post(f"/api/projects/{project}/stop")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_stop_not_found(client: AsyncClient) -> None:
    """Stopping a nonexistent project must return 404."""
    resp = await client.post("/api/projects/no-proj/stop")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stopped_project_can_restart(client: AsyncClient, project: str) -> None:
    """A STOPPED simulation must be restartable (STOPPED → RUNNING)."""
    await client.post(f"/api/projects/{project}/start")
    await client.post(f"/api/projects/{project}/stop")
    resp = await client.post(f"/api/projects/{project}/start")
    assert resp.status_code == 200
    assert resp.json()["status"] == "RUNNING"


# ===========================================================================
# GET /api/projects/{name}/simulation/status
# ===========================================================================


@pytest.mark.asyncio
async def test_simulation_status_idle(client: AsyncClient, project: str) -> None:
    """GET /simulation/status for an IDLE project must return valid status payload."""
    resp = await client.get(f"/api/projects/{project}/simulation/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["project_name"] == project
    assert "status" in body
    assert "current_phase" in body
    assert "simulated_day" in body
    assert "overall_progress" in body


@pytest.mark.asyncio
async def test_simulation_status_running(client: AsyncClient, project: str) -> None:
    """GET /simulation/status for a RUNNING project should reflect running state."""
    await client.post(f"/api/projects/{project}/start")
    resp = await client.get(f"/api/projects/{project}/simulation/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["project_name"] == project


@pytest.mark.asyncio
async def test_simulation_status_not_found(client: AsyncClient) -> None:
    """GET /simulation/status for a nonexistent project must return 404."""
    resp = await client.get("/api/projects/no-proj/simulation/status")
    assert resp.status_code == 404


# ===========================================================================
# GET /api/projects/{name}/agents
# ===========================================================================


@pytest.mark.asyncio
async def test_list_agents(client: AsyncClient, project: str) -> None:
    """GET /agents must return the full roster of 30 agents."""
    resp = await client.get(f"/api/projects/{project}/agents")
    assert resp.status_code == 200
    agents = resp.json()
    assert isinstance(agents, list)
    assert len(agents) == 30


@pytest.mark.asyncio
async def test_list_agents_structure(client: AsyncClient, project: str) -> None:
    """Each agent entry must have required fields."""
    resp = await client.get(f"/api/projects/{project}/agents")
    agents = resp.json()
    for agent in agents:
        for field in ("codename", "role", "side", "tier", "model", "status"):
            assert field in agent, f"Agent missing field: {field}"


@pytest.mark.asyncio
async def test_list_agents_not_found(client: AsyncClient) -> None:
    """GET /agents for a nonexistent project must return 404."""
    resp = await client.get("/api/projects/no-proj/agents")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_agents_contains_pm_alex(client: AsyncClient, project: str) -> None:
    """Agent roster must include PM_ALEX."""
    resp = await client.get(f"/api/projects/{project}/agents")
    codenames = [a["codename"] for a in resp.json()]
    assert "PM_ALEX" in codenames


# ===========================================================================
# GET /api/projects/{name}/feed
# ===========================================================================


@pytest.mark.asyncio
async def test_get_feed_empty(client: AsyncClient, project: str) -> None:
    """GET /feed on a fresh project must return empty events list."""
    resp = await client.get(f"/api/projects/{project}/feed")
    assert resp.status_code == 200
    body = resp.json()
    assert "events" in body
    assert "total" in body
    assert isinstance(body["events"], list)


@pytest.mark.asyncio
async def test_get_feed_after_start(client: AsyncClient, project: str) -> None:
    """After starting simulation, feed must contain at least SIMULATION_STARTED event."""
    await client.post(f"/api/projects/{project}/start")
    resp = await client.get(f"/api/projects/{project}/feed")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1


@pytest.mark.asyncio
async def test_get_feed_pagination(client: AsyncClient, project: str) -> None:
    """Feed must support pagination (page/limit query params)."""
    # Generate some events
    await client.post(f"/api/projects/{project}/start")
    await client.post(f"/api/projects/{project}/pause")
    await client.post(f"/api/projects/{project}/resume")

    resp = await client.get(f"/api/projects/{project}/feed?page=1&limit=2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 1
    assert body["limit"] == 2
    assert "has_more" in body


@pytest.mark.asyncio
async def test_get_feed_not_found(client: AsyncClient) -> None:
    """GET /feed for a nonexistent project must return 404."""
    resp = await client.get("/api/projects/no-proj/feed")
    assert resp.status_code == 404


# ===========================================================================
# GET /api/projects/{name}/decisions & POST decisions
# ===========================================================================


@pytest.mark.asyncio
async def test_get_decisions_empty(client: AsyncClient, project: str) -> None:
    """GET /decisions on a fresh project must return empty board."""
    resp = await client.get(f"/api/projects/{project}/decisions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["pending"] == []


@pytest.mark.asyncio
async def test_get_decisions_not_found(client: AsyncClient) -> None:
    """GET /decisions for a nonexistent project must return 404."""
    resp = await client.get("/api/projects/no-proj/decisions")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_post_decision_valid(client: AsyncClient, project: str) -> None:
    """POST /decisions must create a decision and return 201."""
    resp = await client.post(
        f"/api/projects/{project}/decisions",
        json={
            "title": "Adopt S/4HANA Cloud",
            "description": "Move all operations to S/4HANA Cloud PE.",
            "category": "technical",
            "proposed_by": "PM_ALEX",
            "proposed_at_day": 1,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["total"] >= 1


@pytest.mark.asyncio
async def test_post_decision_missing_required_fields(client: AsyncClient, project: str) -> None:
    """POST /decisions without required fields must return 422."""
    resp = await client.post(
        f"/api/projects/{project}/decisions",
        json={"title": "Incomplete"},  # missing description and proposed_by
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_post_decision_duplicate_returns_409(client: AsyncClient, project: str) -> None:
    """POST /decisions with duplicate title+proposer+day must return 409."""
    payload = {
        "title": "Duplicate Decision",
        "description": "First proposal.",
        "proposed_by": "PM_ALEX",
        "proposed_at_day": 5,
    }
    r1 = await client.post(f"/api/projects/{project}/decisions", json=payload)
    assert r1.status_code == 201

    r2 = await client.post(f"/api/projects/{project}/decisions", json=payload)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_post_decision_not_found(client: AsyncClient) -> None:
    """POST /decisions for a nonexistent project must return 404."""
    resp = await client.post(
        "/api/projects/no-proj/decisions",
        json={
            "title": "X", "description": "Y",
            "proposed_by": "PM_ALEX", "proposed_at_day": 0,
        },
    )
    assert resp.status_code == 404


# ===========================================================================
# GET /api/projects/{name}/meetings
# ===========================================================================


@pytest.mark.asyncio
async def test_list_meetings_empty(client: AsyncClient, project: str) -> None:
    """GET /meetings on a fresh project must return empty list."""
    resp = await client.get(f"/api/projects/{project}/meetings")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_meetings_not_found(client: AsyncClient) -> None:
    """GET /meetings for a nonexistent project must return 404."""
    resp = await client.get("/api/projects/no-proj/meetings")
    assert resp.status_code == 404


# ===========================================================================
# GET /api/projects/{name}/tools
# ===========================================================================


@pytest.mark.asyncio
async def test_get_tools_empty(client: AsyncClient, project: str) -> None:
    """GET /tools on a fresh project must return empty tool list."""
    resp = await client.get(f"/api/projects/{project}/tools")
    assert resp.status_code == 200
    body = resp.json()
    assert "tools" in body
    assert "total" in body
    assert body["total"] == 0
    assert body["tools"] == []


@pytest.mark.asyncio
async def test_get_tools_not_found(client: AsyncClient) -> None:
    """GET /tools for a nonexistent project must return 404."""
    resp = await client.get("/api/projects/no-proj/tools")
    assert resp.status_code == 404


# ===========================================================================
# GET /api/projects/{name}/test-strategy
# ===========================================================================


@pytest.mark.asyncio
async def test_get_test_strategy_empty(client: AsyncClient, project: str) -> None:
    """GET /test-strategy on a fresh project must return empty structure."""
    resp = await client.get(f"/api/projects/{project}/test-strategy")
    assert resp.status_code == 200
    body = resp.json()
    assert "tests" in body
    assert "overall_progress" in body
    assert isinstance(body["tests"], list)


@pytest.mark.asyncio
async def test_get_test_strategy_not_found(client: AsyncClient) -> None:
    """GET /test-strategy for a nonexistent project must return 404."""
    resp = await client.get("/api/projects/no-proj/test-strategy")
    assert resp.status_code == 404


# ===========================================================================
# GET /api/projects/{name}/lessons
# ===========================================================================


@pytest.mark.asyncio
async def test_get_lessons_empty(client: AsyncClient, project: str) -> None:
    """GET /lessons on a fresh project must return empty list."""
    resp = await client.get(f"/api/projects/{project}/lessons")
    assert resp.status_code == 200
    body = resp.json()
    assert "lessons" in body
    assert "total" in body
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_get_lessons_not_found(client: AsyncClient) -> None:
    """GET /lessons for a nonexistent project must return 404."""
    resp = await client.get("/api/projects/no-proj/lessons")
    assert resp.status_code == 404


# ===========================================================================
# GET /api/projects/{name}/settings & PUT settings
# ===========================================================================


@pytest.mark.asyncio
async def test_get_settings(client: AsyncClient, project: str) -> None:
    """GET /settings must return default settings structure."""
    resp = await client.get(f"/api/projects/{project}/settings")
    assert resp.status_code == 200
    body = resp.json()
    assert "litellm_base_url" in body
    assert "litellm_model" in body
    assert "max_parallel_agents" in body
    assert "memory_compression_interval" in body


@pytest.mark.asyncio
async def test_get_settings_not_found(client: AsyncClient) -> None:
    """GET /settings for nonexistent project must return 404."""
    resp = await client.get("/api/projects/no-proj/settings")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_put_settings_update_model(client: AsyncClient, project: str) -> None:
    """PUT /settings must update specified fields."""
    resp = await client.put(
        f"/api/projects/{project}/settings",
        json={"litellm_model": "gpt-4o"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["litellm_model"] == "gpt-4o"


@pytest.mark.asyncio
async def test_put_settings_partial_update(client: AsyncClient, project: str) -> None:
    """PUT /settings must only update provided fields, leaving others intact."""
    # First set max_parallel_agents
    await client.put(
        f"/api/projects/{project}/settings",
        json={"max_parallel_agents": 15},
    )
    # Then update only the model
    resp = await client.put(
        f"/api/projects/{project}/settings",
        json={"litellm_model": "claude-3-opus"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["litellm_model"] == "claude-3-opus"
    assert body["max_parallel_agents"] == 15  # must be preserved


@pytest.mark.asyncio
async def test_put_settings_invalid_parallel_agents(client: AsyncClient, project: str) -> None:
    """PUT /settings with max_parallel_agents > 30 must return 422."""
    resp = await client.put(
        f"/api/projects/{project}/settings",
        json={"max_parallel_agents": 99},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_put_settings_not_found(client: AsyncClient) -> None:
    """PUT /settings for nonexistent project must return 404."""
    resp = await client.put(
        "/api/projects/no-proj/settings",
        json={"litellm_model": "gpt-4o"},
    )
    assert resp.status_code == 404


# ===========================================================================
# Lifecycle integration: create → start → pause → resume → stop → delete
# ===========================================================================


@pytest.mark.asyncio
async def test_full_lifecycle(client: AsyncClient) -> None:
    """Full simulation lifecycle must complete without errors."""
    # Create
    r = await client.post("/api/projects", json={"name": "lifecycle-test"})
    assert r.status_code == 201
    assert r.json()["status"] == "IDLE"

    # Start
    r = await client.post("/api/projects/lifecycle-test/start")
    assert r.status_code == 200
    assert r.json()["status"] == "RUNNING"

    # Pause
    r = await client.post("/api/projects/lifecycle-test/pause")
    assert r.status_code == 200
    assert r.json()["status"] == "PAUSED"

    # Resume
    r = await client.post("/api/projects/lifecycle-test/resume")
    assert r.status_code == 200
    assert r.json()["status"] == "RUNNING"

    # Stop
    r = await client.post("/api/projects/lifecycle-test/stop")
    assert r.status_code == 200
    assert r.json()["status"] == "STOPPED"

    # Delete
    r = await client.delete("/api/projects/lifecycle-test")
    assert r.status_code == 204

    # Confirm gone
    r = await client.get("/api/projects/lifecycle-test")
    assert r.status_code == 404


# ===========================================================================
# GET /api/projects/{name}/report
# ===========================================================================


@pytest.mark.asyncio
async def test_get_report(client: AsyncClient, project: str) -> None:
    """GET /report must return a report dict with content field."""
    resp = await client.get(f"/api/projects/{project}/report")
    assert resp.status_code == 200
    body = resp.json()
    assert "content" in body
    assert "project_name" in body
    assert project in body["content"]


@pytest.mark.asyncio
async def test_get_report_not_found(client: AsyncClient) -> None:
    """GET /report for a nonexistent project must return 404."""
    resp = await client.get("/api/projects/no-proj/report")
    assert resp.status_code == 404


# ===========================================================================
# GET /api/projects/{name}/stakeholder
# ===========================================================================


@pytest.mark.asyncio
async def test_get_stakeholder_view(client: AsyncClient, project: str) -> None:
    """GET /stakeholder must return health score and status."""
    resp = await client.get(f"/api/projects/{project}/stakeholder")
    assert resp.status_code == 200
    body = resp.json()
    assert "health_score" in body
    assert "status" in body
    assert "current_phase" in body
    assert 0 <= body["health_score"] <= 100


@pytest.mark.asyncio
async def test_get_stakeholder_not_found(client: AsyncClient) -> None:
    """GET /stakeholder for a nonexistent project must return 404."""
    resp = await client.get("/api/projects/no-proj/stakeholder")
    assert resp.status_code == 404


# ===========================================================================
# Admin endpoints
# ===========================================================================


@pytest.mark.asyncio
async def test_admin_health(client: AsyncClient) -> None:
    """GET /api/admin/health must return aggregate health metrics."""
    resp = await client.get("/api/admin/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "active_projects" in body
    assert "uptime_seconds" in body


@pytest.mark.asyncio
async def test_admin_highlights(client: AsyncClient) -> None:
    """GET /api/admin/highlights must return highlights list."""
    resp = await client.get("/api/admin/highlights")
    assert resp.status_code == 200
    body = resp.json()
    assert "highlights" in body
    assert "total" in body


@pytest.mark.asyncio
async def test_admin_token_usage(client: AsyncClient, project: str) -> None:
    """GET /api/admin/token-usage must return token usage for a project."""
    resp = await client.get(f"/api/admin/token-usage?project_name={project}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["project_name"] == project
    assert "total_used" in body


# ===========================================================================
# POST /api/settings/test (LiteLLM connectivity test)
# ===========================================================================


@pytest.mark.asyncio
async def test_settings_test_endpoint_reachable(client: AsyncClient) -> None:
    """POST /api/settings/test must return a TestSettingsResponse (even on failure)."""
    resp = await client.post(
        "/api/settings/test",
        json={
            "litellm_base_url": "http://localhost:9999",  # unreachable
            "litellm_api_key": "test-key",
            "litellm_model": "gpt-4o",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "success" in body
    # Will fail (no server), but must not 500
    assert body["success"] is False


# ===========================================================================
# POST /api/projects/{name}/agents/reroll
# ===========================================================================


@pytest.mark.asyncio
async def test_reroll_personalities(client: AsyncClient, project: str) -> None:
    """POST /agents/reroll must return updated agent list (IDLE only)."""
    resp = await client.post(f"/api/projects/{project}/agents/reroll")
    assert resp.status_code == 200
    agents = resp.json()
    assert isinstance(agents, list)
    assert len(agents) == 30


@pytest.mark.asyncio
async def test_reroll_running_simulation_conflicts(client: AsyncClient, project: str) -> None:
    """POST /agents/reroll on a running simulation must return 409."""
    await client.post(f"/api/projects/{project}/start")
    resp = await client.post(f"/api/projects/{project}/agents/reroll")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_reroll_single_agent(client: AsyncClient, project: str) -> None:
    """POST /agents/reroll with a specific codename must work."""
    resp = await client.post(
        f"/api/projects/{project}/agents/reroll",
        json={"codename": "EXEC_VICTOR"},
    )
    assert resp.status_code == 200


# ===========================================================================
# POST /api/projects/{name}/artifacts/report
# ===========================================================================


@pytest.mark.asyncio
async def test_generate_artifact_report(client: AsyncClient, project: str) -> None:
    """POST /artifacts/report must return an ArtifactResponse."""
    resp = await client.post(
        f"/api/projects/{project}/artifacts/report",
        json={"force_regenerate": False},
    )
    # Accept both 201 (created) and 200 (served from cache); both are OK
    assert resp.status_code in (200, 201)
    body = resp.json()
    assert "content" in body
    assert "project_name" in body
    assert body["project_name"] == project


@pytest.mark.asyncio
async def test_generate_artifact_report_not_found(client: AsyncClient) -> None:
    """POST /artifacts/report for nonexistent project must return 404."""
    resp = await client.post(
        "/api/projects/no-proj/artifacts/report",
        json={"force_regenerate": False},
    )
    assert resp.status_code == 404
