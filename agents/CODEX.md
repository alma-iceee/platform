# Codex Backend Guide

## Role

Codex is the backend/Django agent for Ordo.

Communicate with Almas in Russian using Cyrillic.

Before backend changes, read:

- `agents/AGENTS.md`
- `agents/PROJECT_CONTEXT.md`

## Backend Responsibilities

Codex owns:

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

- the user explicitly asks for it, or
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
