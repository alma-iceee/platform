# Agent Access Profiles

This file defines the intended access profile for each agent role.

It is the source of truth for local agent configuration until each tool/runtime has its own committed config format.

## PM

PM should have:

- read access only inside `agents/`
- write access to `agents/inbox/**`
- optional write access to `agents/outbox/**` only when updating prompt metadata or documenting PM notes

PM should not have:

- application code access outside `agents/`
- docker access
- Playwright/browser automation
- test execution
- commit/push permissions

## Backend

Backend should have:

- read access to the whole repository
- write access to backend and supporting project files in scope of assigned tasks
- write access to `agents/outbox/**`
- git read-only commands such as `git status`, `git diff`, `git show`
- docker access for Django checks, migrations, tests, and app-local execution

Recommended docker command family:

```text
docker compose -f docker-compose.dev.yml run --rm web ...
```

Backend should not have by default:

- destructive git commands
- commit/push permissions
- unrestricted package installation

## Frontend

Frontend should have:

- read access to the whole repository
- write access to:
  - `apps/ordo/workspaces/templates/workspaces/**`
  - `static/workspaces/**`
  - `prototypes/**`
  - `agents/outbox/**`
- Playwright/browser automation access
- optional git read-only commands

Frontend does not need by default:

- docker access
- Python/backend write access
- migrations
- commit/push permissions

If frontend starts needing routine Django checks or local container bootstrapping, add docker access later.

## QA

QA should have:

- read access to the whole repository
- write access to `agents/outbox/**`
- git read-only commands such as `git status`, `git diff`, `git show`
- docker access for checks and tests
- Playwright/browser automation access

QA should not have by default:

- broad feature-code write access
- destructive git commands
- commit/push permissions

## Notes

- `agents/inbox/**` and `agents/outbox/**` task files are git-ignored except their `README.md` files.
- Runtime-specific config should follow this file where possible.
- If a runtime does not yet have a committed local config format, update this file first and mirror it later in that runtime.
