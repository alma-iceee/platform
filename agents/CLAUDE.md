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

## Design System (workspace shell)

All tokens live in `static/workspaces/shell.css :root`. Always use tokens — never hardcode colors. When asked to build any UI (a card, a control, a list, etc.), reuse this system by default.

### Surfaces (elevation ladder)

- Page background: darkest — `--bg-dark` (#06162c) / `--bg-panel` (#091b33).
- `--surface-control` (#162c50, solid) — interactive controls: buttons, workspace selector, search box, inputs, icon buttons, profile button.
- `--surface-raised` (gradient from #162c50) — cards / containers: panels, overview cards, `.settings-card`, list/table body.
- `--surface-control` and `--surface-raised` are the SAME tone today but kept as two tokens on purpose (controls vs cards may diverge later). Pick by role, not by color.
- List/table header: lighter (#1d3460) — a raised "shelf" that stands out from the card body.
- Dropdown / overlay menus: darker (#071222) + `backdrop-filter: blur` — "floating" above content.

### Card pattern (use whenever a card is needed)

```css
background: var(--surface-raised);
border: 1px solid var(--border-card);
box-shadow: var(--shadow-card), var(--hairline-top);
border-radius: 18px; /* 18–22px */
```
`--hairline-top` is a 1px top light line that creates the raised feel. For smaller cards use just `--hairline-top` without `--shadow-card`.

### Accents (RGB channels for alpha)

Use `rgba(var(--x), a)` with: `--violet-rgb`, `--cyan-rgb`, `--blue-rgb`, `--sky-rgb`, `--danger-rgb`. Solid accents: `--accent-blue`, `--accent-blue-dark`, `--accent-violet`.

### Text

`--text-main` (#fff), `--text-bright` (headings / emphasis), `--text-soft`, `--text-muted`, `--text-active` (blue — active nav/items).

### Depth helpers

`--border-soft`, `--border-card`, `--shadow-card`, `--hairline-top`.

### Headings

- Page header: `<h1>` in `.settings-page-header` (34px / 800) with a bottom border divider.
- Section subheader: `<h2>` in `.settings-header` — has a `::before` colored accent bar (blue gradient).
- Keep text minimal: drop decorative eyebrows ("Workspace shell") and redundant descriptions.

### List/table that must fit the viewport

Use `.workspace-content--fit` (page doesn't scroll) + `.settings-section--fill` (one section fills remaining height, its `.access-table-wrap` scrolls). Table header is `position: sticky`.

### Conventions

- Lucide is pinned locally at `static/workspaces/vendor/lucide.min.js` (never the CDN).
- Shared JS goes in `static/workspaces/shell.js`, not inline in templates.
- This design system is living — update this section when Almas changes the style.

## Frontend Check

After template/CSS-only changes, run when possible:

```bash
docker compose -f docker-compose.dev.yml run --rm web python manage.py check --settings=config.settings.dev
```
