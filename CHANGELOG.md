# Changelog

All notable changes to `stepfun-image` are documented in this file.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-06-25

### Added

- `stepfun_audio/voices.py` — HTTP voice preview + clone
- `stepfun_audio/tts_stream.py` — WebSocket streaming TTS
- `stepfun_audio/realtime.py` — WebSocket single-turn realtime voice chat
- CLI subcommands: `tts-stream`, `realtime`, `voices preview`, `voices clone`
- 13 new pytest cases (6 voices + 7 ws_streams). Total: 37 passing.
- `websocket-client>=1.6` runtime dependency.

### Known Limitations

- `/step_plan/v1/audio/voices/preview` returns a gateway 404 (text/plain),
  not a JSON API error — the route is not deployed at the Step Plan gateway
  yet, despite the docs. Code is ready; will work when routed.
- The TTS WebSocket text-submission event name is provisional (`tts.text`).
  If you see "Connection lost" after `tts.create`, adjust per the
  open-platform docs at https://platform.stepfun.com/zh/api-reference/audio/ws-audio

See [docs/incidents/2026-06-25-step-plan-voice-endpoints.md](docs/incidents/2026-06-25-step-plan-voice-endpoints.md)
for the full probe transcript and reasoning.

## [0.1.0] - 2026-06-25

### Added

- Initial release
- `stepfun_image.client.StepFunImageClient` (text-to-image + image edit)
- `stepfun_image.ccswitch` loader that auto-reads the StepFun API key from
  the CCSwitch SQLite database (`~/.cc-switch/cc-switch.db`); `STEP_API_KEY`
  env var overrides.
- CLI: `stepfun t2i ...`, `stepfun edit ...`, `stepfun whoami`
- Cross-platform launchers: `stepfun.cmd` (Windows), `stepfun.sh` (POSIX)
- Claude Code / Codex skill at `~/.claude/skills/stepfun-image/SKILL.md`,
  with a project-local copy in `skill/SKILL.md`
- One-shot bootstrap script `migrate.sh` for fresh machines
- Pytest unit tests (13 cases) covering the CCSwitch loader, CLI arg parsing,
  and request payload shape (mocked)
- GitHub Actions CI on Python 3.10 / 3.11 / 3.12

### Fixed

- First CI run failed because `requirements.txt` had referenced
  `requirements-dev.txt` instead of the other way around. See
  [docs/incidents/2026-06-25-ci-missing-requests.md](docs/incidents/2026-06-25-ci-missing-requests.md)
  for the full post-mortem.

[Unreleased]: https://github.com/mashenmemeimei/stepfun-image/compare/2889745...HEAD
[0.2.0]: https://github.com/mashenmemeimei/stepfun-image/compare/ce08b85...2889745
[0.1.0]: https://github.com/mashenmemeimei/stepfun-image/releases/tag/v0.1.0
