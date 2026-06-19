# Codex Role Launching

The repository keeps role-specific profile templates in `.codex/`:

- `.codex/pm.config.toml`
- `.codex/backend.config.toml`
- `.codex/qa.config.toml`

Codex itself loads active profiles from `$CODEX_HOME`, which is typically:

```text
/home/progse/.codex/
```

So the active profile files should exist there as:

- `/home/progse/.codex/pm.config.toml`
- `/home/progse/.codex/backend.config.toml`
- `/home/progse/.codex/qa.config.toml`

## Launcher

The repo provides `scripts/codex-role-launcher.sh`.

Source it in your shell:

```bash
source /home/progse/Projects/platform/scripts/codex-role-launcher.sh
```

After sourcing, these commands work:

```bash
codex pm
codex backend
codex qa
```

They expand to:

```bash
codex -p <role> -C /home/progse/Projects/platform
```

Any extra arguments are forwarded to Codex.

Examples:

```bash
codex backend
codex backend "Read agents/AGENTS.md and continue"
codex qa --search
```

## Why Not `/codex backend`

`/codex backend` would mean executing a file located exactly at `/codex`.

That is not the normal shell pattern and would require installing a custom executable at the filesystem root. Use:

```bash
codex backend
```

instead.
