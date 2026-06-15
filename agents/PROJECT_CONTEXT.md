# Ordo Project Context

## Project

Ordo is a Django project management platform.

## Product Domain Model

Ordo is intended for a large holding structure:

- A holding contains multiple companies.
- Companies contain departments.
- Departments contain employees through department memberships.
- Every department needs its own task workspace surface: a default department kanban/board for that department's internal work.

The core use case is task management across this organization tree, but collaboration is not limited to one department.

Important product concepts:

- A `Workspace` is the access and collaboration container.
- A company-level workspace has `Workspace.company` set and represents the normal working area for one company.
- A special-purpose workspace can be created when leadership wants to bring together people from multiple companies and departments for a larger initiative.
- Workspace access can be granted to a whole company, one department, or an individual user.
- A `WorkspaceTeam` is a workspace-local grouping of existing workspace access grants. It is not the source of workspace access by itself.
- A `Project` is an initiative/work container separate from departments.
- A department should have its own department board/kanban, but that board is not a `Project`.
- Larger projects may involve several departments within one company.
- Larger cross-company projects may involve several companies and departments from different companies.
- Project visibility is scoped only by project-level team assignment. In the current implementation, projects use `Project.team -> WorkspaceTeam`, and a user sees the project when they match one of that workspace team's access grants.
- Department visibility is separate from project visibility. Departments are a primary workspace navigation item only for company workspaces (`Workspace.company` is set). Cross-company/custom workspaces should not show Departments as a main dashboard/nav entry; departments should appear later as participants inside teams/projects.
- In a company workspace, a user sees their own departments by default. Company directors with company workspace access can see departments for that company.

Example:

- A user works in Company A, Department B.
- The user can have access to Company A's workspace.
- The user should see Department B as an accessible department and later use Department B's department board.
- If leadership creates a cross-company initiative, they can create a separate workspace, grant selected companies/departments/users access to that workspace, then create projects inside it and assign the relevant teams/access.

Modeling guidance:

- Do not model department boards as projects.
- Preserve the distinction between organization structure (`Company`, `Department`), workspace access (`WorkspaceAccessGrant`), workspace-local grouping (`WorkspaceTeam`), and work containers (`Project`).
- Future tasks/kanban should be scoped either to a department board or to a project board. Do not add `Project.department` or `Project.kind=department` for this.
- Do not use legacy `ProjectMembership` for new workspace project access unless explicitly requested. It is still present for compatibility and is tied to legacy `Team`.

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
