# UI and data-loading benchmarks

Run from the repository root using the existing local runtime. These opt-in
benchmarks do not load a speech model, generate audio, download anything, or
use your personal jobs, voices, models, credentials or preferences. Fixtures
and INI settings live in a disposable temporary directory. Production code is
unchanged. Results stay local under the ignored `benchmarks/results/` folder.

## Before and after

```powershell
.\.runtime\Scripts\python.exe -m benchmarks.run --output benchmarks/results/before-1.json
.\.runtime\Scripts\python.exe -m benchmarks.run --output benchmarks/results/before-2.json

# After the agreed optimisation changes, use the identical benchmark and runtime:
.\.runtime\Scripts\python.exe -m benchmarks.run --output benchmarks/results/after-1.json
.\.runtime\Scripts\python.exe -m benchmarks.run --output benchmarks/results/after-2.json
.\.runtime\Scripts\python.exe -m benchmarks.run --compare benchmarks/results/before-1.json benchmarks/results/after-1.json
```

Use the same machine, power mode, runtime and background workload. Avoid running
generation, builds or other tests concurrently. Each command uses a fresh process,
three warmup calls and 15 measured calls per case. Repeat complete runs at least
twice; compare baseline runs to judge noise before attributing a difference to code.
For steadier tail estimates, use `--samples 50` on **both** baseline and after runs.
The default p95 is the slowest of 15 samples, so it is sensitive to interruptions.
There is no automatic performance pass/fail threshold.

The runner refuses to overwrite reports. The comparison rejects differing
benchmark source hashes, fixture versions, runtime/platform metadata, sample
settings or case sets. Reports record the commit and an application-source hash
to identify local edits. They do not store usernames, absolute paths, scripts,
voices or logs. Environment matching cannot identify every hardware or power
setting difference; keep those conditions consistent yourself.

## Workloads and interpretation

- **10, 100 and 500 persisted jobs:** one synthetic script and 20 chunk records
  per job, half complete. Roughly 20% are archived. Cases measure all-manifest
  loading, unchanged visible-list refresh, a title/progress change, an idle poll
  whose one-second refresh is due, and a poll before that deadline. File creation
  and external fixture edits happen outside the timing. Ordering, archive
  filtering, selected job, title and progress are checked after each operation.
- **All four models:** empty cache, partial snapshots, then complete recorded
  snapshots. Three revisions per repository include shared model files. Small
  placeholders exercise metadata discovery and record checks, not weight loading,
  integrity hashing or multi-gigabyte throughput. Cases time an all-model scan,
  the settings inspector refresh, and its real Preferences-controller callback
  into the model manager. The last case substitutes only the Preferences dialog
  shell to avoid credential/background work; it is not a full Preferences-open
  measurement.

Wall-clock latency includes Qt event processing and deferred widget deletion at
the fixed offscreen size of 1200 × 800 and scale 1. It does not measure desktop
compositor latency or perceived smoothness on a physical display. App polling
timers are stopped and the actual poll method is invoked explicitly. Filesystem
caches are warm; these are not cold-disk or clean-install benchmarks.

JSON reports retain every sample plus median, p95, min and max. Process CPU time
is supplementary: Windows clock granularity can produce zero for short calls.
One extra **untimed** profiling pass counts manifest loads, inventory inspections,
record loads, job-card construction and snapshot publication. These counts help
explain improvements without adding profiler overhead to latency samples.
Negative median changes in the comparison mean faster; a p95 ratio below 1 means
lower tail latency. For very short calls, compare absolute milliseconds as well
as percentages.

These cases target the first four reviewed optimisations. Startup, first opening
of Preferences, log-event throughput, real speech speed, GPU memory and output
quality need separate workloads if those areas change. Benchmarks complement
functional tests and manual checks; speed alone does not establish equivalence.
Keep synthesis settings and watermarking unchanged.

## Checking the harness

```powershell
.\.runtime\Scripts\python.exe -m unittest tests.test_benchmark_reports -q
.\.runtime\Scripts\python.exe -m benchmarks.run --sizes 3 --samples 3 --warmups 1 --output benchmarks/results/check.json
```

The small run validates actual Qt/data paths. The report tests protect percentile
calculation, warmup exclusion and incompatible-comparison rejection. Timing runs
are deliberately not part of CI; only the report tests join the normal test gate.
