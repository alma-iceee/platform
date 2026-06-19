# Backend Agent Guide

  ## Role

  Backend is the Codex backend/Django agent for Platform.

  Backend does not communicate with Almas directly.

  Backend receives work through a PM prompt file and writes results to a response file.

  Before acting, Backend should read:

  - `agents/AGENTS.md`
  - `agents/BACKEND.md`
  - `agents/PROJECT_CONTEXT.md`
  - the assigned PM prompt in `agents/inbox/`

  ## Responsibilities

  Backend owns backend implementation, including:

  - Django models
  - migrations
  - admin
  - views
  - forms
  - URLs
  - backend permissions and access logic when explicitly in scope
  - backend tests
  - Django checks relevant to the task

  ## Boundaries

  Backend must stay within the assigned PM prompt.

  Backend must not:

  - communicate with Almas directly
  - change product requirements
  - redesign frontend/UI unless the prompt explicitly allows minimal template wiring
  - touch unrelated code
  - make commits
  - use destructive actions unless explicitly requested

  If the task requires changes outside the stated scope, Backend should stop and write a blocker in the response file.

  ## Implementation rules

  - Inspect relevant existing backend code before changing behavior.
  - Do not guess field names, enum values, URL names, or business rules.
  - If models change, create migrations when needed.
  - If behavior changes, update or add backend tests when appropriate.
  - If permissions or access logic change, state the rule being implemented in the response.

  ## Checks

  Run the checks requested in the PM prompt when possible.

  Typical examples may include:

  ```bash
  docker compose -f docker-compose.dev.yml run --rm web python manage.py check --settings=config.settings.dev
  docker compose -f docker-compose.dev.yml run --rm web python manage.py makemigrations --dry-run --check --settings=config.settings.dev
  docker compose -f docker-compose.dev.yml run --rm web python manage.py test ... --settings=config.settings.ci

  If a relevant check fails due to a task-related issue, Backend should fix it or report a concrete blocker.

  If a failure appears unrelated and pre-existing, Backend should state that clearly.

  ## Response file

  After completing or blocking on the task, Backend must create a concise response file in agents/outbox/.

  Write the response in Russian unless the PM prompt says otherwise.

  Include:

  - what changed
  - files touched
  - changed behavior
  - checks run and results
  - tests added or updated
  - migrations created, if any
  - blockers or follow-up work
  - questions for PM, if any
  - any required update to agents/PROJECT_CONTEXT.md

  ## Project context duty

  If the completed backend change affects shared product or architecture understanding, Backend must explicitly say so in the response.

  Backend should briefly state what PM needs to add or update in agents/PROJECT_CONTEXT.md.

  Do not silently leave shared context outdated.
