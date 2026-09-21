# AGENTS.md

Herdr plugin that equalizes, cycles, and resizes pane layouts.

## Map

1. Read how it works: `ai-artifacts/_index.md`, then `README.md` and `docs/`.
2. Change the code (`src/cli.py`, `src/layouts.py`, `herdr-plugin.toml`).
3. Compile: `python3 -m py_compile src/cli.py src/layouts.py`.
4. Test: `python3 -m unittest discover -s test -v`.

How-it-works docs belong in `ai-artifacts/`. Keep them current when architecture or behavior changes. The folder is new. Start at `_index.md`, which points at `README.md` and `docs/`. Deeper agent docs grow there.

## Commands

Python 3.10+.

```sh
python3 -m unittest discover -s test -v
python3 -m py_compile src/cli.py src/layouts.py
```

This repo has no GitHub Actions workflows. Gate before push:

```sh
python3 -m unittest discover -s test -v && python3 -m py_compile src/cli.py src/layouts.py
```

Optional live e2e. Run only inside Herdr with the plugin linked:

```sh
python3 test/e2e_live.py
```

Link a local checkout, then reload config:

```sh
herdr plugin link ~/projects/my-repos/herdr-pane-layouts
herdr server reload-config
```

## Git commits

Never include Cursor (or any Cursor agent/bot) as git author, committer, or in a Co-authored-by / similar trailer.
