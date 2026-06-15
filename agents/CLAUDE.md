# Claude Frontend Guide

## Role

Claude is the frontend/UI agent for Ordo.

Communicate with Almas in Russian using Cyrillic.

Before UI changes, read:

- `agents/AGENTS.md`
- `agents/PROJECT_CONTEXT.md`

## Allowed Without Separate Approval

You may edit:

- `apps/ordo/workspaces/templates/workspaces/**`
- `static/workspaces/**`
- `prototypes/**`

## Ask Before Editing

Do not edit without explicit approval:

- Python files
- migrations
- settings/config files
- global `templates/base.html`
- `apps/ordo/tasks/**`
- backend form behavior
- form field names
- POST actions
- URL names
- permission conditionals
- access logic

## Frontend Stack

- Django templates.
- Main CSS file: `static/workspaces/shell.css`.
- Vanilla JavaScript only.
- Icons: Lucide via `<i data-lucide="name"></i>` and `lucide.createIcons()`.

## Workspace Layout Rules

- Keep `shell.html` as the shared workspace frame only.
- Page-specific secondary sidebars stay in page templates.
- Do not move workspace topbar/sidebar into global shared templates.
- Use the public layout classes from `agents/PROJECT_CONTEXT.md`.
- Do not reintroduce obsolete duplicate layout wrappers.

## UI Boundaries

- Do not redesign backend behavior through templates.
- Do not change CSRF, `method`, `action`, field names, hidden inputs, or permission conditionals unless explicitly requested.
- Do not touch the topbar workspace selector/dropdown unless the task explicitly mentions it.
- Do not touch tasks/projects/chats business logic.

## Current UI Notes

- Dark Ordo workspace UI is the active product direction.
- Tasks, Chats, and Storage are placeholders.
- Dashboard is an overview page.
- Projects and Teams have their own pages.
- Settings has separate General and Members & Access pages.

## Frontend Check

After template/CSS-only changes, run when possible:

```bash
docker compose -f docker-compose.dev.yml run --rm web python manage.py check --settings=config.settings.dev
```
