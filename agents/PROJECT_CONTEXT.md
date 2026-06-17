# Ordo Project Context

## Project

Ordo is a Django project management platform.

## Product Domain Model

Ordo is intended for a large holding structure:

- A holding contains multiple companies.
- Companies contain departments.
- Departments contain employees through department memberships.
- Every department needs its own task workspace surface: a default department kanban/board for that department's internal work.

## Organization Roles and Access Intent

Users get organization subscriptions through company and department memberships.

Target company membership roles:

- company head/director: can see and manage everything inside their company.
- employee: regular company member.
- observer: read-only company participant.

Target department membership roles:

- department chief/head: can see and manage everything inside their department.
- employee: regular department member.
- observer: read-only department participant.

Target system roles:

- none: normal user with only explicit company/department/workspace access and no system-role privileges by itself.
- ceo: can see and manage everything across all companies, departments, workspaces, teams, and projects.

Current implementation note:

- `CompanyMembership.Role` currently has `director` and `member`.
- `DepartmentMembership.Role` currently has `chief` and `member`.
- `User.SystemRole` currently has `none`, `general_director`, and `ceo`.
- `general_director` currently keeps global workspace visibility/management behavior, but must not be treated like `ceo` for workspace creation or Settings access.
- Do not assume observer support exists until the models, migrations, permissions, seed data, and UI are updated together.

Access intent:

- Company and department memberships define a user's place in the organization tree.
- Company workspaces are implicitly visible to users with a matching `CompanyMembership`.
- Custom/cross-company workspace access is explicit through `WorkspaceAccessGrant`.
- A company employee can open their company's own company workspace through `CompanyMembership`.
- Additional workspace visibility is grant-scoped: normal users can also see workspaces through direct user grants, company grants, or department grants that match their memberships.
- Company membership gives access to that company's own company workspace (`Workspace.company` matches the membership company).
- Workspace selector/default selection should list accessible company workspaces before cross-company/custom workspaces.
- Inside a company workspace, regular employees see only departments where they have `DepartmentMembership`.
- Company workspace settings are managed only through the administrative/backoffice layer. The normal workspace UI must not expose company workspace settings, and direct settings/access mutation requests for company workspaces must be forbidden for every user, including `ceo`, `general_director`, staff, and superusers.
- Custom/cross-company workspace creation and workspace Settings access are CEO-only in the normal workspace UI. Backend views must enforce this too; hiding buttons/tabs is not enough.
- Creating or editing workspace teams and projects is not finalized as CEO-only. Treat team/project mutation permissions as an open product decision until leadership delegation rules are confirmed.
- Company directors should be able to manage company-scoped workspace data for their own company.
- Department chiefs should be able to manage department-scoped data for their own department.
- CEO-level users should bypass normal organization scoping and manage everything.

The core use case is task management across this organization tree, but collaboration is not limited to one department.

Important product concepts:

- A `Workspace` is the access and collaboration container.
- A company-level workspace has `Workspace.company` set and represents the normal working area for one company.
- A company-level workspace is a system projection of the organization structure, not a user-managed workspace; its settings/access structure should be changed through admin/backoffice tooling.
- A special-purpose workspace can be created when leadership wants to bring together people from multiple companies and departments for a larger initiative.
- Workspace access can be granted to a whole company, one department, or an individual user.
- `WorkspaceAccessGrant.role` stores workspace permission level for that grant (`owner`, `admin`, `member`, `viewer`).
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
- Tasks/kanban are scoped through `TaskBoard`. A board can represent inbox, workspace-level work, a department board, or a project board. Do not add `Project.department` or `Project.kind=department` for this.
- Do not reintroduce legacy workspace/project membership models. Project visibility should stay on `Project.team -> WorkspaceTeam -> WorkspaceTeamMember -> WorkspaceAccessGrant`.

## Tasks and Boards Backend

The backend task data model exists in `apps/ordo/tasks`.

Implemented models:

- `TaskBoard`
- `TaskColumn`
- `Task`
- `TaskAssignee`
- `TaskObserver`
- `TaskAttachment`

Task board rules:

- Users do not create boards manually in the normal UI.
- Boards are system containers created automatically.
- `TaskBoard.board_type` values:
  - `inbox`
  - `workspace`
  - `department`
  - `project`
- Every board belongs to exactly one `Workspace`.
- `department` boards have `TaskBoard.department` set.
- `project` boards have `TaskBoard.project` set.
- `inbox` and `workspace` boards have neither `department` nor `project`.

Automatic board creation:

- Creating any `Workspace` creates:
  - `Inbox` board
  - `Workspace` board
- Creating a company workspace (`Workspace.company != null`) also creates one department board for every department in that company.
- Creating a custom/cross-company workspace (`Workspace.company is null`) does not create department boards.
- Creating a `Project` creates one project board for that project.
- Creating a `Department` creates a department board only inside company workspaces for that department's company.
- Deletion/deactivation behavior is not designed yet. Do not add deletion workflows for task boards unless explicitly requested.

Default columns:

Every auto-created board gets the same default columns:

- `To do` (`key=todo`, semantic type `todo`)
- `In progress` (`key=in-progress`, semantic type `active`)
- `Review` (`key=review`, semantic type `review`)
- `Awaiting approval` (`key=awaiting-approval`, semantic type `review`)
- `Done` (`key=done`, semantic type `done`, `is_done=True`)

Task rules:

- Every `Task` belongs to one `Workspace`.
- Every `Task` belongs to one `TaskBoard`.
- Every `Task` belongs to one `TaskColumn`.
- Task status is derived from `Task.column`, not from a separate `Task.status` field.
- A newly created unclassified workspace-level task should go into the workspace's `Inbox` board.
- `Task.workspace` must match `TaskBoard.workspace`.
- `Task.column` must belong to `Task.board`.

Task fields currently available:

- `title`
- `description`
- `priority`: `low`, `normal`, `high`, `urgent`
- `due_date`
- `responsible`: one main responsible user, nullable
- `created_by`
- `position`
- `completed_at`

Additional task relations:

- `TaskAssignee`: extra assignees. Use this when more than one person works on the task.
- `TaskObserver`: watchers/observers.
- `TaskAttachment`: uploaded files.

Automation implementation:

- `apps/ordo/tasks/services.py` contains idempotent helpers:
  - `ensure_workspace_task_boards(workspace)`
  - `ensure_company_department_task_boards(workspace)`
  - `ensure_department_task_board(workspace, department)`
  - `ensure_project_task_board(project)`
  - `ensure_default_task_columns(board)`
  - `sync_task_boards()`
- `apps/ordo/tasks/signals.py` creates boards on `Workspace`, `Project`, and `Department` creation.
- Backfill command:

```bash
python manage.py sync_task_boards --settings=config.settings.dev
```

Demo task seed command:

```bash
python manage.py seed_task_demo --settings=config.settings.dev
```

`seed_task_demo` first ensures all task boards/default columns exist, then creates one demo task in each default column of every task board. It is idempotent for its own demo task titles and should not create duplicate demo cards on repeated runs.

Frontend task guidance:

- The Tasks section should use existing `TaskBoard` and `TaskColumn` data.
- Do not add UI for creating/deleting task boards.
- Department boards should appear only in company workspaces.
- Custom/cross-company workspaces should show only inbox/workspace/project task boards, not department boards.
- Project task surfaces should use the project's `TaskBoard`.
- If a task is not assigned to a department or project yet, show it in the workspace `Inbox` board.
- Status labels should come from columns.
- Do not invent a separate task status field in forms or templates.
- Task permissions are not fully implemented yet. Frontend may use the current accessible workspace/project/department context, but backend permission enforcement for task mutations still needs a later pass.

Current workspace sections:

- Dashboard
- Tasks
- Projects
- Teams
- Chats
- Storage
- Settings

Chats and Storage are still placeholder workspace pages. Tasks have backend tables and board automation, but the workspace Tasks UI is not implemented yet.

## Django Apps

Important app areas:

- `apps/ordo/accounts`: custom user and organization membership models.
- `apps/ordo/organizations`: companies and departments.
- `apps/ordo/workspaces`: workspace shell, workspace access, teams, projects, settings.
- `apps/ordo/tasks`: task boards, task columns, tasks, assignees, observers, attachments, and board automation.

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
- A grant has a role:
  - `owner`
  - `admin`
  - `member`
  - `viewer`
- Project/team workspace management rules are not finalized. Do not assume `none` grants management by itself, but also do not hard-code CEO-only for teams/projects without an explicit implementation request.
- Workspace Settings permission is separate from project/team management and is CEO-only for custom/cross-company workspaces. Company workspace Settings are forbidden for everyone in the workspace UI.
- Workspace teams are separate from workspace access.
- `WorkspaceTeam` is workspace-local.
- `WorkspaceTeamMember` links a team to a `WorkspaceAccessGrant`.
- `WorkspaceTeamMember.clean()` validates that team and grant belong to the same workspace.

## Removed Legacy Workspace Models

The old workspace access layer has been removed:

- legacy `Team`
- `WorkspaceMembership`
- `ProjectMembership`

Do not add new code against those models.

## Projects MVP

Projects are separate from Dashboard.

- Dashboard is an overview with quick links.
- Projects page handles project list/detail/create/edit.
- `Project.team` links to `WorkspaceTeam`.
- `Project.created_by` links to the user model.
- Project task boards are implemented in the backend through `TaskBoard(board_type=project, project=project)`.
- Project task UI is not implemented yet.

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

Workspace seed command:

```bash
python manage.py seed_workspace_demo --settings=config.settings.dev
```

It assumes organization data already exists and creates:

- one company workspace per company
- workspace name exactly equal to company name
- `Workspace.company` set to that company
- one company-level `WorkspaceAccessGrant` with `member` role per company workspace
- three cross-company workspaces with `Workspace.company = None`
- workspace-local teams for cross-company project work
- varied team membership examples: company-only teams, department-only/user teams, and mixed company/department/user teams
- resource/mining-themed demo projects linked to those teams

The company-level workspace grant gives all users with a matching `CompanyMembership` access to that company's workspace. The command should not demote existing `admin` or `owner` grants.

Task demo seed command:

```bash
python manage.py seed_task_demo --settings=config.settings.dev
```

Run it after organization and workspace seed data when the UI needs populated task boards. It creates demo task cards for every existing board/column and does not seed workspaces, teams, projects, companies, departments, or users.

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
