# Frontend Agent Guide

## Role

Frontend is the Claude frontend/UI agent for Ordo.

Frontend does not communicate with Almas directly by default.

Frontend receives work through a PM prompt file and returns results through a response file. If blocked, write the blocker and the exact question for PM into the response file.

Before UI changes, read:

- `agents/AGENTS.md`
- `agents/PROJECT_CONTEXT.md`
- `agents/FRONTEND.md`
- the assigned PM prompt file in `agents/inbox/`

## Prompt Mode

Frontend follows the assigned PM prompt.

If the prompt says `obsujdenie`, `обсуждение`, "discuss", "analyze", "plan", asks for options, or is clarifying product behavior, stay in analysis mode.

In analysis mode:

- Do not edit files.
- Do not run formatters, migrations, tests, or browser automation unless the prompt explicitly asks for that action.
- Write a response file with options, tradeoffs, recommendation, and the next decision needed.

Only implement when the PM prompt clearly asks to implement.

## Allowed Without Separate Approval

You may edit:

- `apps/ordo/workspaces/templates/workspaces/**`
- `static/workspaces/**`
- `prototypes/**`

## Ask Before Editing

Do not edit without explicit approval in the assigned PM prompt:

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

If a protected area is required, stop and write a blocker in the response file. Do not ask Almas directly.

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

### Page layout & headers

- Page indent lives on `.workspace-content` (top 16px, left 18px to match the sidebar) — never re-pad individual headers; the header and content move together from this one place.
- Page header: `<h1>` in `.settings-page-header` (or `.tasks-toolbar`), sized like the sidebar title (**18px / 800**), with a **full-bleed bottom divider** (the header uses negative horizontal margins = the content padding so the line runs edge-to-edge, from the sidebar to the right wall).
- Every page header starts with a left icon: `<h1><i data-lucide="…" class="page-header-icon"></i>Title</h1>`. Use the icon of the matching secondary-sidebar nav item; if the page has no secondary sidebar, use that section's shell-sidebar icon (dashboard `layout-dashboard`, tasks `square-check-big`, projects `kanban`, teams `users-round`, settings `sliders-horizontal`/`users`, etc.).
- Section subheader: `<h2>` in `.settings-header` — has a `::before` colored accent bar (blue gradient).
- Keep text minimal: drop decorative eyebrows ("Workspace shell") and redundant descriptions.

### Settings-style forms (card-less)

For settings/general-type pages, put labelled fields straight in the section — no `.settings-card` wrapper. Use `<form class="settings-form settings-form--stack">` with each field wrapped in `.settings-field` (label + control + optional `.settings-note`). `.settings-input-prefix` gives an inline prefixed input (e.g. `ordo.kz/` + slug).

### Default button

There is ONE primary action button — the **default button** — and it must look the same on every content page. Use it for all main page actions (New task, New project, Add user, Add department, Add company, Save changes, etc.). Do not invent per-page button variants with different size, padding, color, or font.

Markup (icon + label in a `<span>`):

```html
<button type="button" class="shell-button" data-modal-open="…">
  <i data-lucide="plus" aria-hidden="true"></i><span>New task</span>
</button>
```

- Base class is always `shell-button` (solid blue gradient). Variants: `shell-button-secondary` (Cancel / ghost), `shell-button-danger` (Remove / destructive).
- Need it aligned/positioned (e.g. pushed to the right of a header row)? Add a **position-only** modifier class that sets just `margin-left`/layout — never one that restyles color, size, padding, or font. Example: `.access-group-add { margin-left: auto; }` keeps the default button look while moving it right.
- Do not create smaller "ghost" add buttons on individual pages. The Members & Access add buttons were a one-off variant and were normalized back to the default button.

### Modals

There is ONE shared modal type — reuse it for every "open X in a popup with a blurred backdrop" request (e.g. "make a modal for create workspace"). Do not invent new modal markup.

Markup (place the overlay once, near the end of `shell.html` body so it can open from anywhere):

```html
<div class="modal-overlay" id="my-modal">
  <div class="modal">
    <div class="modal-head"><h2>Title</h2><button class="modal-close" data-modal-close>&times;</button></div>
    <div class="modal-body"> … </div>
    <div class="modal-foot"><span class="spacer"></span> … buttons … </div>
  </div>
</div>
```

- Open from a trigger with `data-modal-open="my-modal"`. Close via `data-modal-close`, backdrop click, or Escape — all handled generically in `shell.js` (no per-modal JS).
- The overlay blurs the page (`backdrop-filter`) and uses the card surface (`--surface-raised`).
- For forms shared between a modal and a page, extract the fields into a partial and include it in both (see `workspaces/workspaces/_create_form_fields.html`). Keep a plain page version as a no-JS fallback (the trigger's `href` still points to it).

### List/table that must fit the viewport

Use `.workspace-content--fit` (page doesn't scroll) + `.settings-section--fill` (one section fills remaining height, its `.access-table-wrap` scrolls). Table header is `position: sticky`.

### Conventions

- Lucide is pinned locally at `static/workspaces/vendor/lucide.min.js` (never the CDN).
- Shared JS goes in `static/workspaces/shell.js`, not inline in templates.
- This design system is living. If the assigned work changes the style direction, mention the needed `PROJECT_CONTEXT.md` or `FRONTEND.md` update in the response file.

## Local Login (Playwright)

To work with the running app through Playwright, you can log in with the local dev admin account. The same credentials work for both the app login and the Django admin (`/admin/`):

- Email: `admin@ordo.local`
- Password: `admin`

Use this only against the local dev environment to drive/inspect the UI. Do not put these or any other credentials into committed files beyond this dev note.

## Frontend Check

After template/CSS-only changes, run when possible:

```bash
docker compose -f docker-compose.dev.yml run --rm web python manage.py check --settings=config.settings.dev
```

## Response File

After completing or blocking on the assigned prompt, create a concise response file in `agents/outbox/`.

Write the response in Russian unless the assigned prompt says otherwise.

Include:

- what changed;
- files touched;
- visual behavior changed;
- checks run and results;
- browser/Playwright notes, if used;
- blockers or follow-up work;
- questions for PM, if any;
- anything PM must add to `PROJECT_CONTEXT.md`.
