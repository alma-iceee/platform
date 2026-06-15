# Ordo Project Context

## Project

Ordo is a Django project management platform.

Current workspace sections:

- Dashboard
- Tasks
- Projects
- Teams
- Chats
- Storage
- Settings

Tasks, Chats, and Storage are still placeholder workspace pages.

## Django Apps

Important app areas:

- `apps/ordo/accounts`: custom user and organization membership models.
- `apps/ordo/organizations`: companies and departments.
- `apps/ordo/workspaces`: workspace shell, workspace access, teams, projects, settings.
- `apps/ordo/tasks`: task area. Do not touch without explicit instruction.

## Workspace Template Architecture

- `templates/base.html` is global only:
  - HTML document structure
  - head/body
  - static loading
  - favicon
  - global blocks
- `apps/ordo/workspaces/templates/workspaces/shell.html` is the workspace frame only:
  - topbar
  - main icon sidebar
  - workspace content slot
- Page templates extend `workspaces/shell.html` and fill `workspace_content`.
- Page-specific secondary sidebars belong inside page templates, not in `shell.html`.

Page templates are grouped by section:

- `workspaces/dashboard/dashboard.html`
- `workspaces/settings/settings.html`
- `workspaces/projects/`
- `workspaces/teams/`
- `workspaces/tasks/`
- `workspaces/chats/`
- `workspaces/storage/`
- `workspaces/profile/`

## Core Workspace CSS Classes

Public layout classes:

- `workspace-layout`
- `topbar`
- `sidebar`
- `workspace-sidebar`
- `workspace-main`

Avoid reintroducing obsolete duplicate layout systems:

- `app-layout`
- `content-shell`
- `main-area`
- `main-surface`
- `workspace-secondbar`

## Frontend Stack

- Django templates under `apps/ordo/workspaces/templates/workspaces/`.
- Main workspace CSS: `static/workspaces/shell.css`.
- Vanilla JavaScript, usually inline in templates.
- Icons: Lucide via `<i data-lucide="name"></i>` and `lucide.createIcons()`.
- Current visual direction: dark Ordo workspace UI with blue/cyan accents.

## Workspace Access Architecture

- `WorkspaceAccessGrant` controls who can access/open/use a workspace.
- A grant targets exactly one of:
  - company
  - department
  - user
- Workspace teams are separate from workspace access.
- `WorkspaceTeam` is workspace-local.
- `WorkspaceTeamMember` links a team to a `WorkspaceAccessGrant`.
- `WorkspaceTeamMember.clean()` validates that team and grant belong to the same workspace.

## Legacy Workspace Models

These still exist and must not be deleted unless explicitly requested:

- legacy `Team`
- `WorkspaceMembership`
- `ProjectMembership`

Do not rewrite project/task/chat access logic unless explicitly instructed.

## Projects MVP

Projects are separate from Dashboard.

- Dashboard is an overview with quick links.
- Projects page handles project list/detail/create/edit.
- `Project.team` links to `WorkspaceTeam`.
- `Project.created_by` links to the user model.
- No tasks, workflows, or boards are implemented inside projects yet.

## Organization Seed Data

Organization-only seed command:

```bash
python manage.py seed_organization_demo --settings=config.settings.dev
```

It seeds only:

- companies
- departments
- users
- company and department memberships

It must not seed:

- workspaces
- teams
- projects
- tasks
- workspace access grants
- dashboard data

## Common Checks

Prefer Makefile commands when available:

```bash
make check
make test
make makemigrations
make migrate
```

Useful dev commands:

```bash
make up
make up-d
make down
make logs
make shell
make bash
```

Direct Docker equivalents:

```bash
docker compose -f docker-compose.dev.yml run --rm web python manage.py check --settings=config.settings.dev
docker compose -f docker-compose.dev.yml run --rm web python manage.py test apps.ordo.workspaces --settings=config.settings.ci
```

Local equivalents:

```bash
python manage.py check --settings=config.settings.dev
python manage.py test apps.ordo.workspaces --settings=config.settings.ci
```
