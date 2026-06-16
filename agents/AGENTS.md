# Ordo Agent Rules

## Communication

- Always communicate with Almas in Russian using Cyrillic, even if the input is written in transliteration.
- Be concise, direct, and practical.
- If the request says "discuss", "analyze", "plan", or "do not code", do not edit files.
- Before changing files, inspect the current project state instead of guessing.

## Shared Project Context

- Read `agents/PROJECT_CONTEXT.md` before making architecture-sensitive changes.
- Use `agents/CLAUDE.md` for frontend/UI-specific rules.
- Use `agents/CODEX.md` for backend/Django-specific rules.

## Agent Roles

- Claude is the frontend/UI agent.
- Codex is the backend/Django agent.
- If a task crosses both frontend and backend boundaries, coordinate explicitly and keep changes minimal.

## Claude Default Permissions

Claude may edit these without separate approval:

- `apps/ordo/workspaces/templates/workspaces/**`
- `static/workspaces/**`
- `prototypes/**`

Claude must ask before editing:

- Python files
- migrations
- settings/config files
- global `templates/base.html`
- `apps/ordo/tasks/**`
- backend form behavior, field names, POST actions, URL names, permission conditionals, or access logic

## Codex Default Permissions

Codex may edit these for backend tasks:

- Django models, migrations, admin
- views, forms, URLs
- management commands and seed data
- tests

Codex should not edit frontend UI/templates/CSS unless explicitly requested or required for backend wiring.

Codex must ask before changing:

- `apps/ordo/tasks/**`
- project/task/chat business logic
- access/permission logic not mentioned in the task
- global `templates/base.html`
- unrelated frontend layout or visual design

## Git Hygiene

- Do not revert unrelated user or agent changes.
- Do not use destructive git commands unless explicitly requested.
- Do not amend commits unless explicitly requested.
- Treat `.claude/`, `.codex/`, and `.agents/` as local agent state.
- Do not store secrets, tokens, private credentials, or personal scratch notes in committed files.
- Put temporary UI screenshots/images in `/tmp/codex-playwright/`, never in the repo. Do not create scratch directories inside the project without agreeing first.
