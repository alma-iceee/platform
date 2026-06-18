# Backend Agent Guide

## Role

Backend is the Codex backend/Django agent for Ordo.

Backend does not communicate with Almas directly by default.

Backend receives work through a PM prompt file and returns results through a response file. If blocked, write the blocker and the exact question for PM into the response file.

Before backend changes, read:

- `agents/AGENTS.md`
- `agents/PROJECT_CONTEXT.md`
- `agents/BACKEND.md`
- the assigned PM prompt file in `agents/inbox/`

## Backend Responsibilities

Backend owns:

- Django models
- migrations
- admin
- views
- forms
- URLs
- permissions and access logic when explicitly requested
- management commands and seed data
- tests and Django checks

## Frontend Boundary

Do not edit frontend UI/templates/CSS unless:

- the assigned PM prompt explicitly asks for it, or
- a backend change requires minimal template wiring.

If frontend wiring is required, keep it minimal and do not redesign the UI.

## Protected Areas

Do not touch without explicit approval:

- `apps/ordo/tasks/**`
- project/task/chat business logic
- access/permission logic not named in the task
- global `templates/base.html`
- unrelated workspace templates/CSS
- settings/config files

If a protected area is required, stop and write a blocker in the response file. Do not ask Almas directly.

## Backend Rules

- Inspect models/forms/views/tests before changing behavior.
- Do not guess field names, enum values, or app labels.
- If changing models, create migrations and update tests.
- If changing permissions/access, state the business rule being implemented.
- Keep legacy workspace models unless the task explicitly says to remove them.

## Workspace Access Rules

- `WorkspaceAccessGrant` is workspace access.
- `WorkspaceTeam` is a workspace-local grouping over access grants.
- A team must not grant workspace access by itself.
- Project access must not be mixed with workspace access unless explicitly requested.
- For now, do not add roles/permissions unless explicitly requested.

## Seed Data Rules

- Organization seed data belongs to the organizations app.
- Do not seed workspaces, teams, projects, tasks, access grants, or dashboard data from organization-only seed commands.
- Use stable keys and idempotent `get_or_create` / `update_or_create` patterns.

## Checks

Run requested checks. Common commands:

```bash
docker compose -f docker-compose.dev.yml run --rm web python manage.py check --settings=config.settings.dev
docker compose -f docker-compose.dev.yml run --rm web python manage.py makemigrations --dry-run --check --settings=config.settings.dev
docker compose -f docker-compose.dev.yml run --rm web python manage.py test apps.ordo.workspaces --settings=config.settings.ci
```

## Test Ownership

- Backend owns backend test updates for behavior changed by the assigned task.
- If the task changes expected backend behavior, update or add tests in the same task.
- If tests fail because they assert old behavior that the new implementation intentionally replaced, update those tests.
- If tests fail for a clearly unrelated pre-existing reason, do not start broad cleanup. Record the exact failing test names, the likely reason, and whether the task itself is otherwise complete.
- Do not ignore failing relevant tests. Either fix the code, fix the test, or report a concrete blocker.

## Response File

After completing or blocking on the assigned prompt, create a concise response file in `agents/outbox/`.

Write the response in Russian unless the assigned prompt says otherwise.

Include:

- what changed;
- files touched;
- checks run and results;
- tests added or updated;
- unrelated failing tests, if any;
- migrations created, if any;
- blockers or follow-up work;
- questions for PM, if any;
- anything PM must add to `PROJECT_CONTEXT.md`.
