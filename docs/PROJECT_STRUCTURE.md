# Project Structure

This repository keeps user-facing launchers in the project root so existing shortcuts, GUI buttons, and scheduled tasks continue to work. Larger documentation and Streamlit panel implementations are grouped into folders.

## Root

- `README.md`, `README.zh-CN.md`: public project introduction.
- `OpenClaw Control Center GUI.cmd`: main local GUI launcher.
- `start-*.ps1`, `stop-*.ps1`: compatibility launchers used by the GUI and existing shortcuts.
- `factor_lab.py`, `strategy_debug_lab.py`, `telegram_template_lab.py`: compatibility wrappers for Streamlit panels.
- `build_dynamic_alt_universe.py`, `evaluate_backtest_stability.py`, `publish_dashboard_public_data.py`: active workflow scripts kept in root because daemon workflow arguments reference these exact paths.

## `apps/streamlit`

Streamlit panel implementations:

- `factor_lab.py`: local factor dashboard.
- `strategy_debug_lab.py`: strategy backtest/debug dashboard.
- `telegram_template_lab.py`: Telegram template editor.

## `docs/guides`

Operational guides, tuning notes, lab documentation, and workflow references.

## `docs/project`

Project-level introductions and overview documents.

## `site`

Public website and Vue dashboard source.

## `server`

Server-side scripts that publish read-only dashboard data.

## `scripts`

Windows maintenance helpers and migration/CLI utilities.

## `user_data`

Freqtrade runtime configuration, strategies, notebooks, and local generated data. Large runtime data remains ignored by Git.
