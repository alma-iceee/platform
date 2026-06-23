  # Ordo Project Context

  ## Project

  Ordo is a Django project management platform.

  ## Product Domain Model

  Ordo is intended for a large holding structure:

  - A holding contains multiple companies.
  - Companies have a stable, unique ASCII `Company.slug`; Russian/Kazakh names are transliterated when an explicit slug is not supplied.
  - Companies contain departments.
  - Departments reference a canonical `DepartmentType` through `Department.type`.
  - A company can have at most one department of each type; department types are shared across companies.
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
  - ceo: can see and manage all user-facing work across companies, departments, workspaces, projects, and tasks. `WorkspaceTeam` is visible read-only; CEO may change which automatic team is linked to a project.

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
  - Company workspace settings are managed only through the administrative/backoffice layer. The normal workspace UI must not expose company workspace settings, and direct settings/access mutation requests for company
  workspaces must be forbidden for every user, including `ceo`, `general_director`, staff, and superusers.
  - Custom/cross-company workspace creation and workspace Settings access are CEO-only in the normal workspace UI. Backend views must enforce this too; hiding buttons/tabs is not enough.
  - Creating and editing projects is allowed for CEO users in every workspace and for company directors only in their own company workspace.
  - `WorkspaceTeam` is a system-managed projection. Accessible teams may be listed and viewed read-only, but no user role may create/edit a team or change its composition.
  - Company directors should be able to manage company-scoped workspace data for their own company.
  - Department chiefs should be able to manage department-scoped data for their own department.
  - CEO-level users should bypass normal organization scoping and manage everything.

  Current workspace/team behavior:

  - Team list/detail/composition routes are GET-only and render read-only data.
  - Public team creation/edit/member mutation forms and handlers have been removed; non-GET requests return `405`.
  - `member` provides working access, including moving tasks on accessible boards; `viewer` remains read-only for task mutation. Neither role grants workspace management.
  - Project mutation does not use this broader rule; it allows CEO globally and a matching company director only inside that company's company workspace.

  The core use case is task management across this organization tree, but collaboration is not limited to one department.

  Important product concepts:

  - A `Workspace` is the access and collaboration container.
  - A company-level workspace has `Workspace.company` set and represents the normal working area for one company.
  - A company-level workspace is a system projection of the organization structure, not a user-managed workspace; its settings/access structure should be changed through admin/backoffice tooling.
  - A special-purpose workspace can be created when leadership wants to bring together people from multiple companies and departments for a larger initiative.
  - Workspace access can be granted to a whole company, one department, or an individual user.
  - `WorkspaceAccessGrant.role` stores workspace permission level for that grant (`owner`, `admin`, `member`, `viewer`).
  - A `WorkspaceTeam` is a read-only, workspace-local grouping of department access grants. It is not the source of workspace access by itself.
  - Department teams are system-managed: one team per `DepartmentType` represented in the workspace's company/department access scope.
  - Automatic team members are department grants only. Company and user grants never become automatic team members directly.
  - A `Project` is an initiative/work container separate from departments.
  - A department should have its own department board/kanban, but that board is not a `Project`.
  - Larger projects may involve several departments within one company.
  - Larger cross-company projects may involve several companies and departments from different companies.
  - Project visibility is scoped only by project-level team assignment. In the current implementation, projects use `Project.team -> WorkspaceTeam`, and a user sees the project when they match one of that workspace
  team's access grants.
  - Department visibility is separate from project visibility. Departments are a primary workspace navigation item only for company workspaces (`Workspace.company` is set). Cross-company/custom workspaces should not
  show Departments as a main dashboard/nav entry; departments may appear through the read-only team linked to a project.
  - In a company workspace, a user sees their own departments by default. Company directors with company workspace access can see departments for that company.

  Example:

  - A user works in Company A, Department B.
  - The user can have access to Company A's workspace.
  - The user should see Department B as an accessible department and later use Department B's department board.
  - If leadership creates a cross-company initiative, they can create a separate workspace, grant selected companies/departments/users access to that workspace, then create projects inside it and assign the relevant
  departments/users and access. The UI may show the resulting automatic team and its departments, but must not offer manual team composition controls.

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
  - `TaskComment`
  - `TaskCommentAttachment`
  - `TaskDiscussion`
  - `TaskDiscussionMessage`
  - `TaskDiscussionMessageAttachment`

  Every task has one automatically created discussion. Task comments and discussion messages are separate chronological streams and each supports its own file attachments. Task discussions inherit access from the task; there are no separate discussion participants or video-call models.

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
  - `created_by`
  - `position`
  - `completed_at`

  Additional task relations:

  - `TaskAssignee`: all responsible/assigned users. There is no legacy single `responsible` field.
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

  `seed_task_demo` first ensures all task boards/default columns exist, then creates one demo task in each default column of every task board. It is idempotent for its own demo task titles and should not create duplicate
  demo cards on repeated runs. Demo assignees/observers are selected through `task_board_user_queryset(board)`, and repeated runs remove stale demo participant links that no longer satisfy board access.

  Frontend task guidance:

  - The Tasks section uses existing TaskBoard and TaskColumn data.
  - Do not add UI for creating/deleting task boards.
  - Department boards should appear only in company workspaces.
  - Custom/cross-company workspaces should show only inbox/workspace/project task boards, not department boards.
  - Project task surfaces should use the project's TaskBoard.
  - If a task is not assigned to a department or project yet, show it in the workspace Inbox board.
  - Status labels should come from columns.
  - Do not invent a separate task status field in forms or templates.

  Current task UI status:

  - Workspace Tasks UI is already implemented.
  - The current Tasks page shows accessible inbox/workspace/department/project boards inside the current workspace context.
  - The page renders kanban columns/cards, supports drag-and-drop between columns, and integrates with create/edit/view modal flows.
  - Drag-and-drop uses workspaces:task-move with AJAX/fetch and X-Requested-With: XMLHttpRequest, with client-side rollback on failure.
  - Create/edit are wired to the backend endpoints below.
  - `New task`, add-task controls, edit fields, and participant controls render only with full task mutation permission. Working members retain drag/status movement on accessible boards without edit controls.
  - Assignee/observer multi-select UI is implemented and uses the board-scoped `task_users` context.
  - The task view modal remains available read-only to users who can see the task and shows author, assignees, observers, description, and status metadata.
  - Comments and discussion are connected to backend JSON endpoints and support their own attachments.
  - Dedicated project-detail task surface, task delete, and general task attachment wiring are not implemented yet.
  - List/Calendar task views are currently inactive placeholders.

  Task create/edit backend MVP:

  - Form class: apps/ordo/tasks/forms.py::TaskForm.
  - Create endpoint: workspaces:task-create / /<workspace-slug>/tasks/create/.
  - Edit endpoint: workspaces:task-edit / /<workspace-slug>/tasks/<task_id>/edit/.
  - Both endpoints are POST-first actions. GET redirects back to the task board.
  - For create, pass current board either in query string and/or POST field:

  /<workspace-slug>/tasks/create/?board=<board-id>

  - On success and validation failure, the backend redirects back to:

  /<workspace-slug>/tasks/?board=<board-id>

  - Create/edit fields currently supported:
      - title
      - description
      - board
      - column
      - priority
      - due_date
      - assignees
      - observers

  - assignees and observers are preserved on edit when the fields are not present in POST. This prevents partial edit forms from accidentally clearing existing people.
  - If the frontend renders assignee/observer controls and wants the backend to sync them, include the fields normally when values are selected.
  - If the frontend renders assignee/observer controls and wants to intentionally clear all values, include hidden markers:

  <input type="hidden" name="assignees__present" value="1">
  <input type="hidden" name="observers__present" value="1">

  - Without those markers, an omitted assignees or observers field means "leave existing values unchanged".
  - When a task changes board, omitted existing people are still validated against the target board; the update is rejected if stale participants would lose access.
  - If column is omitted on create, backend defaults to the board's todo column, then to the first column by position.
  - Task assignee/observer choices use `task_board_user_queryset(board)`: only active users with working access to the selected workspace/department/project board are available. The same queryset is used by `TaskForm`, so forged POST values for inaccessible users fail backend validation.
  - Attachments are not wired into create/edit yet. A frontend upload button may be shown disabled/non-functional for now.
  - Delete task is not implemented.

  Task collaboration JSON endpoints:

  - GET `/<workspace-slug>/tasks/<task-id>/collaboration/` (`workspaces:task-collaboration`) returns the task comments and discussion messages.
  - POST `/<workspace-slug>/tasks/<task-id>/comments/` (`workspaces:task-comment-create`) creates a comment.
  - POST `/<workspace-slug>/tasks/<task-id>/discussion/messages/` (`workspaces:task-discussion-message-create`) creates a discussion message.
  - Both POST endpoints accept `multipart/form-data`; text is sent as `body` and zero or more files as repeated `attachments` fields.
  - Browser `fetch` calls must include Django's `X-CSRFToken` header. When sending `FormData`, do not set `Content-Type` manually.
  - A comment requires non-empty `body`. A discussion message requires either non-empty `body` or at least one attachment.
  - Successful POST responses use HTTP 201 and return the created serialized object. Validation errors use HTTP 400 with `ok=false`, `error`, and field-level `errors`.
  - Serialized comments/messages include author identity, `is_own`, timestamps, and attachment name/URL metadata.
  - Collaboration endpoints require authentication and enforce the same workspace/department/project board visibility used by the Tasks page. Inaccessible tasks return 404.

  Drag/drop move endpoint:

  POST /<workspace-slug>/tasks/<task_id>/move/

  - Django URL name: workspaces:task-move.
  - POST fields:
      - column: required TaskColumn.id
      - position: optional integer, defaults to current task position if omitted

  - The endpoint is intentionally small and does not require full TaskForm.
  - It only moves a task to another column inside the same task board. It does not move tasks between boards.
  - For AJAX/fetch, send header X-Requested-With: XMLHttpRequest.
  - AJAX success response:

  {
    "ok": true,
    "task": {
      "id": 123,
      "board": 10,
      "column": 55,
      "position": 4
    }
  }

  - AJAX validation errors return JSON with ok=false and HTTP 400.
  - Non-AJAX POST redirects back to the task board.

  Task mutation permissions:

  - `ceo` can create, edit, manage participants, and move tasks on every task board.
  - A company director has full task mutation rights inside their own company's company workspace.
  - A department chief has full task mutation rights on their department board and on project boards where their exact department participates in the project's internal `WorkspaceTeam`.
  - A working member can move any task on a board they can access, without gaining task edit or participant-management rights; assignment is not required.
  - Workspace/project/board visibility remains mandatory, so membership in Company A does not expose Company B without a separate applicable access grant.
  - Create/edit validate both the original/selected board and the submitted target board, preventing board changes from bypassing authorization.
  - Comments and discussion messages keep task visibility-based access and do not require task mutation permission.

  ## Django Apps

  Important app areas:

  - apps/ordo/accounts: custom user and organization membership models.
  - apps/ordo/organizations: companies and departments.
  - apps/ordo/workspaces: workspace shell, workspace access, teams, projects, settings.
  - apps/ordo/tasks: task boards, task columns, tasks, assignees, observers, attachments, and board automation.

  Currently registered scaffold areas:

  - apps/ordo/files
  - apps/ordo/notifications
  - apps/ordo/integrations/telegram_gateway

  These apps are registered but currently remain scaffold-level with no meaningful shared backend domain behavior recorded yet.

  ## Workspace Template Architecture

  - templates/base.html is global only:
      - HTML document structure
      - head/body
      - static loading
      - favicon
      - global blocks

  - apps/ordo/workspaces/templates/workspaces/shell.html is the workspace frame only:
      - topbar
      - main icon sidebar
      - workspace content slot

  - Page templates extend workspaces/shell.html and fill workspace_content.
  - Page-specific secondary sidebars belong inside page templates, not in shell.html.

  Page templates are grouped by section:

  - workspaces/dashboard/dashboard.html
  - workspaces/settings/general.html
  - workspaces/settings/members_access.html
  - workspaces/projects/
  - workspaces/teams/
  - workspaces/tasks/
  - workspaces/chats/
  - workspaces/storage/
  - workspaces/profile/

  Settings uses _settings_sidebar.html as a secondary sidebar for its pages.

  ## Core Workspace CSS Classes

  Public layout classes:

  - workspace-layout
  - topbar
  - sidebar
  - workspace-sidebar
  - workspace-main

  Common reusable UI classes currently in use:

  - form/input/button layer:
      - shell-input
      - shell-button
      - shell-button-secondary
      - shell-button-danger
      - settings-form
      - settings-field
      - settings-label
      - settings-message

  - modal layer:
      - modal-overlay
      - modal
      - modal-head
      - modal-body
      - modal-foot

  - list/table/card layer:
      - access-table
      - workspace-table
      - workspace-table-cell
      - teams-grid
      - team-card
      - settings-empty-state

  Avoid reintroducing obsolete duplicate layout systems:

  - app-layout
  - content-shell
  - main-area
  - main-surface
  - workspace-secondbar

  Design tokens live in static/workspaces/shell.css under :root (--bg-*, --accent-*, --text-*, and related RGB/alpha helpers). Prefer using existing tokens instead of hardcoded new hex values.

  ## Frontend Stack

  - Django templates under apps/ordo/workspaces/templates/workspaces/.
  - Main workspace CSS: static/workspaces/shell.css.
  - Shared workspace JS: static/workspaces/shell.js.
  - Vanilla JavaScript, with some section-specific inline scripts in templates.
  - Icons: Lucide via <i data-lucide="name"></i> and lucide.createIcons().
  - Current visual direction: dark Ordo workspace UI with blue/cyan accents.

  Shared JS patterns currently in use:

  - Lucide icon initialization.
  - Sidebar collapse/expand state persisted in localStorage, including anti-flash inline handling in the shell <head>.
  - Generic modal open/close behavior via data-modal-open / data-modal-close, including backdrop/Escape closing.
  - Generic dropdown helpers.
  - Section-specific UI logic such as Tasks behavior and dependent selects may still live in inline template scripts.

  ## Workspace Access Architecture

  - WorkspaceAccessGrant controls who can access/open/use a workspace.
  - A grant targets exactly one of:
      - company
      - department
      - user

  - A grant has a role:
      - owner
      - admin
      - member
      - viewer

  - Project mutation is allowed for CEO users globally and for company directors in their own company workspace.
  - Workspace Settings permission is separate from project management and is CEO-only for custom/cross-company workspaces. Company workspace Settings are forbidden for everyone in the workspace UI.
  - Workspace teams are separate from workspace access.
  - WorkspaceTeam is workspace-local.
  - WorkspaceTeamMember links a team to a WorkspaceAccessGrant.
  - WorkspaceTeamMember.clean() validates that team and grant belong to the same workspace.
  - Automatic department teams have `WorkspaceTeam.department_type` set and are unique per workspace/type.
  - Company access is expanded into system-generated department grants for team membership; these grants are hidden from the normal access list and removed when no longer covered by workspace access.

  Current UI/backend access-grant behavior:

  - Settings access forms in the normal workspace UI currently create grants with default role member.
  - The normal workspace UI does not currently let the user choose or edit WorkspaceAccessGrant.role.
  - Team membership always references a grant from the same workspace.
  - Team list/detail/composition routes are read-only; manual team forms and mutation handlers have been removed.
  - Project Members shows the linked team and composition. Only CEO can switch the project to another active automatic team.
  - Automatic teams are synchronized after workspace, access-grant, department, and department-type changes.

  ## Removed Legacy Workspace Models

  The old workspace access layer has been removed:

  - legacy Team
  - WorkspaceMembership
  - ProjectMembership

  Do not add new code against those models.

  ## Projects MVP

  Projects are separate from Dashboard.

  - Dashboard is an overview with quick links.
  - Projects page handles project list/detail/create/edit.
  - Project.team links to WorkspaceTeam.
  - Project.created_by links to the user model.
  - Project task boards are implemented in the backend through TaskBoard(board_type=project, project=project).
  - A dedicated project-detail task surface is not implemented yet.
  - `WorkspaceProjectForm` currently exposes only name/description and regenerates `Project.slug` from the name on every save. The Project URL field is disabled in UI, so an explicit slug cannot currently be edited through the normal project form.
  - Seed projects may provide explicit semantic English slugs that differ from transliteration of their display names.
  - Project Members exposes CEO-only team selection; all other users see the linked team and its departments read-only.

  ## Workspace UI Sections

  Canonical workspace routing:

  - Workspace context is the first path segment: `/<workspace-slug>/`.
  - Sections use `/<workspace-slug>/tasks/`, `/<workspace-slug>/projects/`, and similar paths.
  - `board` remains a query parameter because it is Tasks page state, not workspace identity.
  - Root `/` redirects to the first accessible canonical workspace URL.
  - Old `/workspaces/.../?workspace=<slug>` routes exist only as transitional compatibility routes and must not be emitted by templates or redirects.
  - Root slugs reserve `accounts`, `admin`, `media`, `new-workspace`, `static`, and `workspaces`.

  Current workspace sections:

  - Dashboard
  - Departments
  - Tasks
  - Projects
  - Chats
  - Storage
  - Settings

  Current implemented vs placeholder status:

  - Implemented and connected:
      - Dashboard
      - Tasks
      - Projects
      - Settings

  - Placeholder or partial:
      - Chats
      - Storage
      - Departments main page

  - Some connected pages still contain demo/static fragments that look real in the UI, especially task modal side content and parts of Members/Access presentation.

  Departments UI note:

  - Departments appears only in company workspaces (Workspace.company is set).
  - The main Departments page is still a placeholder/coming soon surface.
  - Department navigation and department-linked task boards are already real in the workspace UI.

  ## Workspace Form Pattern

  Workspace UI forms currently use a PRG-style invalid form flow:

  - invalid POST form state may be stashed in session
  - the next GET reopens the correct modal/page state with errors
  - this avoids browser resubmission flows

  New workspace forms should preserve this pattern unless a task explicitly changes it.

  ## Login UI

  - templates/accounts/login.html is separate from the workspace shell.
  - The login page currently uses its own template/style layer and is not fully visually unified with the main workspace shell.

  ## Organization Seed Data

  Organization-only seed command:

  python manage.py seed_organization_demo --settings=config.settings.dev

  It also creates the local demo superuser `admin@ordo.local` with password `admin`.

  It seeds only:

  - companies
  - departments
  - users
  - company and department memberships

  Company seed entries may be strings or `{name, slug}` objects. Explicit slugs are preferred for canonical company URLs; string entries use the shared ASCII transliterator.

  It must not seed:

  - workspaces
  - teams
  - projects
  - tasks
  - workspace access grants
  - dashboard data

  Workspace seed command:

  python manage.py seed_workspace_demo --settings=config.settings.dev

  It assumes organization data already exists and creates:

  - one company workspace per company
  - workspace name exactly equal to company name
  - company workspace slug exactly equal to `Company.slug`
  - Workspace.company set to that company
  - one company-level WorkspaceAccessGrant with member role per company workspace
  - three cross-company workspaces with Workspace.company = None
  - automatic department teams derived from the seeded workspace access scope
  - resource/mining-themed demo projects linked to those automatic teams when a department type is available

  The company-level workspace grant gives all users with a matching CompanyMembership access to that company's workspace. The command should not demote existing admin or owner grants.

  Current custom workspace creation behavior:

  - Normal workspace UI allows custom/cross-company workspace creation only for ceo.
  - A newly created custom workspace has Workspace.company = None.
  - The creator receives a direct user WorkspaceAccessGrant with role owner.

  Task demo seed command:

  python manage.py seed_task_demo --settings=config.settings.dev

  Run it after organization and workspace seed data when the UI needs populated task boards. It creates demo task cards for every existing board/column and does not seed workspaces, teams, projects, companies,
  departments, or users.

  ## Auth and Request Protection

  - Authentication is email-based.
  - Email is normalized to lowercase and mirrored into username.
  - Case-insensitive uniqueness is protected at the database level.
  - A global LoginRequiredMiddleware protects the application outside login/static/media routes.
  - Do not assume every protected view is decorated individually; global middleware is part of the current protection model.

  ## Infrastructure Status

  - Current Django settings effectively use SQLite.
  - Docker Compose provisions PostgreSQL and related environment variables, but the current settings do not yet consume them as the active DB configuration.
  - Current prod/staging settings should be treated as scaffold-level configuration, not as fully production-ready infrastructure.

  ## Common Checks

  Prefer Makefile commands when available:

  make check
  make test
  make makemigrations
  make migrate

  Useful dev commands:

  make up
  make up-d
  make down
  make logs
  make shell
  make bash

  Direct Docker equivalents:

  docker compose -f docker-compose.dev.yml run --rm web python manage.py check --settings=config.settings.dev
  docker compose -f docker-compose.dev.yml run --rm web python manage.py test apps.ordo.workspaces --settings=config.settings.ci

  Local equivalents:

  python manage.py check --settings=config.settings.dev
  python manage.py test apps.ordo.workspaces --settings=config.settings.ci
