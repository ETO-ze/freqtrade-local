# Project Structure

This repository keeps the root focused on project metadata and runtime configuration templates. User-facing launchers, Windows scripts, Streamlit apps, and workflow helpers are grouped into dedicated folders.

## Root

- `README.md`, `README.zh-CN.md`: public project introduction.
- `PROJECT_ROADMAP.json`: roadmap markers consumed by dashboard publishing.
- Runtime configuration templates such as `server.openclaw-sync.example.json` remain in the root for easy discovery.

## `apps/streamlit`

Streamlit panel implementations:

- `factor_lab.py`: local factor dashboard.
- `strategy_debug_lab.py`: strategy backtest/debug dashboard.
- `telegram_template_lab.py`: Telegram template editor.

## `apps/desktop`

Desktop GUI implementation:

- `control_center_gui.py`: OpenClaw + Freqtrade control center.

## `launchers`

Windows `.cmd` shortcuts for GUI, dashboards, and daemon start/stop actions.

## `scripts/windows`

PowerShell start/stop/sync/install scripts used by launchers and the GUI.

## `scripts/workflows`

Python workflow helpers for dynamic universe generation, dashboard data publishing, server probing, stability evaluation, and runtime sync.

## `docs/guides`

Operational guides, tuning notes, lab documentation, and workflow references.

## `docs/project`

Project-level introductions and overview documents.

## `site`

Public website and Vue dashboard source.

## `server`

Server-side scripts that publish read-only dashboard data.

## `user_data`

Freqtrade runtime configuration, strategies, notebooks, and local generated data. Large runtime data remains ignored by Git.

