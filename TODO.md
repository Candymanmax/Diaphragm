# Diaphragm — release checklist and roadmap

This is the working checklist for Diaphragm. The immediate goal is a safe,
usable **Private Beta**. The **Public Beta** follows only after private-beta
feedback, clean-install testing, and release documentation are complete.

## How to use this file

- `[x]` means the implementation exists in the codebase. It does not
  automatically mean the release gate has been manually verified.
- `[ ]` means work or verification remains.
- `[P0]` is required for the current release target; `[P1]` is important but
  can follow the first release; `[P2]` is longer-term product work.
- `[Codex]` can usually be implemented or tested locally. `[You]` requires
  your Windows machine, GPU, credentials, or release decision. `[Both]` needs
  code plus your real-world validation. `[GitHub]` requires repository settings
  or permissions outside the working tree.
- Keep the beta sections in priority order. Put new feature ideas in the
  area-based backlog instead of adding another competing priority list.

## Current release targets

### Private Beta — current main priority

Deliver a dependable build to a small group of trusted testers. The private
beta should focus on the existing workflow: install, prepare scripts, create a
job, generate speech, recover from common failures, review output, and provide
useful diagnostics.

### Public Beta — next priority

Open the project more broadly only after the private beta has no unresolved
data-loss or launch blockers, the repository is safe to clone, the supported
environment is documented, and testers have a clear feedback path.
The repository remains private during the private beta; public-repository
security settings and contribution materials are intentionally deferred.

Current application version: `0.1.0-beta.1`

## 1. Private Beta — main priority

### P0 release gates

- [x] [P0] [Codex] Repair the ignored local `.runtime` with a compatible
  64-bit Python environment and install the project dependencies.
- [ ] [P0] [Both] Verify that `launch.bat` recovers clearly from a stale or
  unusable `.runtime` without touching personal library or model data.
- [x] [P0] [Codex] Run the complete automated suite from the documented
  compatible environment with `test.bat`; resolve all current failures,
  including the Windows temporary-path alias failures.
- [x] [P0] [Codex] Add defensive repository ignores for private root-level
  `config.yaml`, scripts, voices, jobs, models, logs, and generated output so
  the repository matches its privacy documentation.
- [x] [Codex] Correct the README’s launch, storage, packaging, and private-data
  descriptions where they differ from the current application paths.
- [ ] [P0] [Codex] Add a concise private-beta quickstart covering Python, CUDA/CPU
  expectations, model installation, voice import, token setup, storage paths,
  logs, and the most common recovery steps.
- [ ] [Both] Verify a fresh launch with no existing layout, configuration,
  library, model cache, or previous job data.
- [ ] [You] Test the app on the Windows hardware you intend to support,
  including the selected CUDA path and CPU fallback where applicable.
- [ ] [Both] Exercise the complete core workflow with a real script and voice:
  create a job, add scripts, run it, pause/cancel if relevant, review output,
  close and reopen the app, and confirm the job remains recoverable.
- [ ] [Both] Verify model installation, model removal, voice import, archive,
  recycle/delete, and retry actions do not remove unrelated personal data.
- [ ] [P0] [Both] Ensure launcher failures leave a useful diagnostic message
  and a discoverable log path without exposing tokens or personal paths.
- [ ] [P0] [Both] Build and smoke-test the intended beta distribution format:
  source plus `launch.bat`, packaged application, or both.
- [ ] [You] Decide the private-beta tester group, distribution method, support
  channel, and minimum hardware/software support policy.
- [ ] [Both] Record known limitations and test results before inviting testers.

### Private-beta exit checklist

- [ ] A new tester can launch without editing source files.
- [ ] A new tester can install or select a supported model and voice.
- [ ] A new tester can complete a short text-to-speech job.
- [ ] A failed, paused, cancelled, or interrupted job remains understandable
  and recoverable.
- [ ] Generated output can be reviewed and opened outside the app.
- [ ] Private scripts, voices, credentials, jobs, models, logs, and audio stay
  outside Git and outside diagnostic messages.
- [ ] The full automated suite and privacy check pass in the documented setup
  on the post-fix GitHub Actions run.
- [ ] Testers have a quickstart, known-limitations list, and feedback route.

### Deliberately out of scope for the first private beta

The queue runner, structured script format, Voices management page, advanced
output comparison, and most long-term automation features can remain in the
backlog unless private-beta feedback makes one of them a release blocker.
Contribution guidance, pull-request templates, and public issue workflows are
also out of scope until contributions are explicitly reopened.

## 2. Public Beta — after Private Beta

### P0 public-release gates

- [ ] [P0] [Both] Review private-beta feedback and resolve all critical launch,
  data-loss, privacy, and generation failures.
- [ ] [P0] [Codex] Test a clean-machine installation at the supported Windows
  scaling factors, including 100%, 125%, and 150% where practical.
- [ ] [P0] [Codex] Produce a reproducible dependency setup or lock/constraints
  file for the supported Python and Torch/Torchaudio combination.
- [ ] [GitHub] Protect `main`, require review before merging, and disable
  force-pushes for the release branch.
- [ ] [GitHub] Enable appropriate dependency and secret scanning for the repo.
- [ ] [GitHub] When the repository becomes public, verify that `SECURITY.md`
  is visible and enable private vulnerability reporting if the repository is
  eligible for that GitHub feature.
- [ ] [Codex] Add a changelog/release-notes format and a public installation
  guide that does not assume developer tools or source edits.
- [ ] [Codex] Add release artifacts, checksums, and signing if the chosen
  distribution format supports them.
- [ ] [Both] Review third-party model, font, icon, and dependency licenses and
  document any required notices.
- [ ] [You] Publish the public-beta release and provide the support/feedback
  process, known limitations, and privacy expectations.

## 3. Completed foundation

These items are implemented and should be preserved while release work is
completed. They still need to remain covered by tests and real-user checks.

### Repository and test foundation

- [x] Repaired the ignored local `.runtime` and documented the isolated
  dependency setup.
- [x] Added the reproducible `test.bat` gate for syntax, headless Qt tests,
  and the current-commit privacy audit.
- [x] Added Windows GitHub Actions for the same test gate and privacy audit;
  the workflow does not download model weights or publish releases.
- [x] Fixed Windows test path comparisons that differed between long and 8.3
  temporary-folder aliases.
- [x] Added defensive repository ignores for private data and generated
  output, and corrected the README's storage and packaging claims.
- [x] Added the ARR-style `LICENSE` and the private-beta `SECURITY.md`.

### Architecture and UI

- [x] Shared state store with typed state slices and signal-driven updates.
- [x] Extracted jobs, scripts, queue, output review, settings, logs, dialogs,
  title bar, and widget components from the main window.
- [x] Job and script lifecycle orchestration moved into focused controllers.
- [x] Cross-widget mutations replaced with controller commands, signals, and
  state updates across the extracted areas.
- [x] Consistent button roles, spacing metrics, Inter font with system fallback,
  empty states, and reusable application dialog cards.
- [x] Dialogs center on the top-level Diaphragm window, including nested
  settings/model prompts, New Job, token entry, search, and Preferences.
- [x] Frameless desktop shell, sidebar navigation, panel visibility, accent
  selection, keyboard shortcuts, and responsive settings inspector.

### Jobs and scripts

- [x] Durable job manifests and segment-level state.
- [x] Interrupted-job recovery, pause, resume, retry, restart, archive, and
  recycle/delete behavior.
- [x] Immediate in-memory jobs and scripts before they are run or saved.
- [x] Dragged-in scripts become in-memory copies and do not delete the source.
- [x] New scripts, Save, Save As, discard protection, line numbers, word and
  character counts, and script selection.
- [x] Compact job cards with status, metadata, archive/delete actions, and job
  empty states.
- [x] One published output per script/job without accidental overwrite.
- [x] Successful temporary chunk cleanup controlled by retention settings.

### Models and generation

- [x] Shared adapter contract and capability registry for Original, Turbo,
  Multilingual V3, and Nano.
- [x] Capability-aware language, event-tag, and generation-control filtering.
- [x] Private Hugging Face model cache with local inventory, install, update,
  verify, repair, remove, and progress states.
- [x] Model-specific runtime profiles, VRAM/RAM monitoring, adaptive splitting,
  CUDA OOM reduction, and optional CPU fallback.
- [x] Per-job voice conditioning reuse across generated chunks and scripts.
- [x] Standardized CPU float32 audio output and persistent generation progress.

### Output, settings, and privacy

- [x] Waveform playback, seeking, output opening, output-folder access, and
  retained-segment editing/regeneration.
- [x] Guided output, diagnostics, error, and no-results states.
- [x] General, Appearance, Library, Models, Storage, Credentials, and Updates
  Preferences pages.
- [x] QSettings UI preferences and validated active configuration in app data.
- [x] Hugging Face credentials stored through Windows Credential Manager.
- [x] Verified library/model-cache migration that preserves the source until a
  copy succeeds.
- [x] Storage usage, log retention, private-path redaction, and safe cleanup.
- [x] `privacy_check.py` for tracked/unignored candidate and history checks.

## 4. Remaining backlog by area

Items below are intentionally not mixed into the immediate release gates. Move
an item into a beta section only when it becomes necessary for that release.

### Jobs and durable data

- [ ] [P1] [Codex] Formalize a versioned job schema and migrations for older
  manifests.
- [ ] [P1] [Codex] Add queue ordering and an optional sequential multi-job
  runner.
- [ ] [P1] [Codex] Add duplicate-job and reusable-job-template actions.
- [ ] [P1] [Codex] Add import/export for a portable job definition without
  private voice data.
- [ ] [P1] [Codex] Surface estimated remaining time and per-stage timing from
  measured history.

### Script authoring and structured input

- [ ] [P1] [Codex] Add non-destructive validation for empty sections,
  unsupported event tags, unusual punctuation, and overly long sentences.
- [ ] [P1] [Codex] Add a split preview showing exactly how text becomes
  generation sections.
- [ ] [P1] [Codex] Add find/replace, clearer undo-history behavior, and optional
  autosave recovery.
- [ ] [P2] [Codex] Define a structured script format for speakers, pauses,
  pronunciation hints, and per-section generation overrides.
- [ ] [P2] [Codex] Add pronunciation dictionaries and reusable
  text-normalization profiles.

### Models and runtime platform

- [ ] [P1] [Codex] Version adapter compatibility against supported Chatterbox
  releases.
- [ ] [P1] [Codex] Add startup diagnostics that distinguish missing files,
  incompatible packages, unsupported hardware, and failed model imports.
- [ ] [P1] [Codex] Add model-specific smoke tests with mocked tensors that do
  not download weights in CI.
- [ ] [P1] [Codex] Record reproducibility metadata with outputs: model,
  revision, settings, seed where supported, sample rate, and runtime device.

### Model manager

- [ ] [P1] [Codex] Add a cancel action that safely waits for Hub file locks and
  preserves resumable partial downloads.
- [ ] [P1] [Codex] Show an exact remote download size only when authoritative
  Hub metadata is available; never display a guessed size.
- [ ] [P1] [Codex] Add repair diagnostics listing missing or damaged logical
  filenames.
- [ ] [P2] [Codex] Add optional model release notes and revision selection behind
  an explicit network action.

### Voice library and conditioning

- [ ] [P1] [Codex] Add a Voices page with name, duration, sample rate, channels,
  loudness, clipping, and compatibility status.
- [ ] [P1] [Codex] Add trim, silence detection, normalization preview, and
  non-destructive reference cleanup.
- [ ] [P1] [Codex] Persist reusable conditioning artifacts when the model API
  provides a stable, versioned serialization contract.
- [ ] [P1] [Codex] Invalidate conditioning when voice bytes, model revision, or
  conditioning controls change.
- [ ] [P2] [Both] Add A/B reference tests and a short standard preview script.

### Adaptive splitting and runtime control

- [ ] [P1] [Codex] Add an optional benchmark that calibrates a new model/GPU
  combination.
- [ ] [P1] [Codex] Improve ETA using voice, model, device, text complexity, and
  measured real-time factor.
- [ ] [P1] [Codex] Explain every automatic size change in concise job
  diagnostics.
- [ ] [P2] [Codex] Add thermal or sustained-load warnings where reliable
  platform metrics exist.

### Output quality and publishing

- [ ] [P1] [Codex] Add automated silence, clipping, duration, and malformed-audio
  checks.
- [ ] [P1] [Codex] Flag unusually short or long speech relative to source text.
- [ ] [P1] [Codex] Add loudness normalization and configurable cross-fades at
  joins.
- [ ] [P2] [Codex] Add side-by-side takes with keep/reject decisions before
  publication.
- [ ] [P1] [Codex] Export WAV, FLAC, and compressed delivery formats with
  metadata controls.
- [ ] [P1] [Codex] Generate a human-readable run report containing warnings and
  runtime metrics.

### Preferences, privacy, and diagnostics

- [ ] [P1] [Codex] Add preference export/import with secrets and personal paths
  removed.
- [ ] [P1] [Codex] Add an in-app privacy audit summarizing what would and would
  not be committed.
- [ ] [P1] [Codex] Add a diagnostics-bundle exporter with automatic token and
  personal-path redaction.
- [ ] [P1] [Codex] Add backup/restore for settings and job metadata without
  model weights.

### Packaging and reliability

- [ ] [P1] [Codex] Add a deterministic environment-repair command that does not
  touch personal library or model data.
- [ ] [P1] [Codex] Add clean-machine packaging tests across Windows scaling
  factors.
- [ ] [P1] [Codex] Add signed release artifacts, checksums, and a manual
  release-notes workflow.
- [ ] [P2] [Codex] Add opt-in crash reports that are locally previewed and
  redacted before sending.

## Definition of done

For a normal feature, do not mark it complete until:

- the UI and backend behavior are connected;
- invalid states are handled without data loss;
- automated tests cover the important path;
- privacy checks still pass; and
- the behavior has been manually exercised when hardware, files, or packaging
  affect the result.

For a beta release, all relevant P0 gates must be checked, the documented
installation must work from a clean start, and the release notes must state any
known limitations that remain.
