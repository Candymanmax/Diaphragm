# Baseline before optimisation

Captured 2026-09-05 against application commit `a85f9ad584e051fd2e24ffda24b057e4472973d3`.
Application source was unchanged; the benchmark tooling and its ignore rule were
local additions. No optimisation has been applied.

Two separate processes completed all 22 cases with 3 warmups and 15 measured
calls per case. Every measured operation passed its correctness checks.
Environment: Windows 11 AMD64, Python 3.12.14, PySide6 6.11.2, 12 logical CPUs,
Qt offscreen at scale 1. See [the protocol](README.md) for scope and limitations.

| Workload | Run 1 median ms | Run 2 median ms | Run 1 p95 ms | Run 2 p95 ms |
| --- | ---: | ---: | ---: | ---: |
| Unchanged refresh, 10 stored / 8 visible jobs | 35.670 | 35.712 | 39.381 | 36.617 |
| Unchanged refresh, 100 stored / 80 visible jobs | 333.428 | 326.371 | 353.500 | 340.001 |
| Unchanged refresh, 500 stored / 400 visible jobs | 2112.730 | 2146.507 | 2390.584 | 2347.923 |
| Load 500 manifests | 114.820 | 110.846 | 133.577 | 126.667 |
| Due idle poll, 500 stored jobs | 2108.722 | 2081.450 | 2260.888 | 2113.894 |
| Scan all complete recorded models | 11.126 | 11.122 | 11.962 | 12.081 |
| Inspector refresh, recorded models | 14.596 | 14.497 | 15.173 | 15.948 |
| Inspector refresh with model manager | 27.280 | 28.153 | 28.559 | 31.067 |

Most medians varied by less than 4% between these unchanged-code runs. The largest
variation was the 100-job due poll, 352.415 ms versus 324.528 ms (7.9% lower).
This is observed variation from two runs, not a statistical confidence bound or
a universal performance threshold. The default p95 is the maximum of 15 samples.

Separate untimed call counts support the first four optimisation proposals:

- A 100-job unchanged refresh constructs 80 visible job cards and loads 100
  manifests. Card reuse should reduce construction work.
- A due idle poll at that size constructs 80 cards and loads 101 manifests,
  including the selected job reload. Sharing the selected manifest from the
  same list refresh should remove that duplicate read.
- Inspector refresh with the model manager performs 9 individual inventory
  inspections and 9 record loads. Sharing inventory results within that refresh
  should reduce duplicated discovery and record loading.

Raw timings, CPU samples, call counts, source hashes and environment metadata
are preserved locally in `results/before-1.json` and `results/before-2.json`.
The results folder is ignored by Git; preserve these files for the after runs.
This summary contains only synthetic-workload measurements.

Validation completed: both full benchmark runs, successful comparison of their
reports, 3 report-unit tests, Python compilation and the current privacy audit.
The full application suite was not rerun for this benchmark-only addition.
Functional and manual verification remain required when application code changes.

After the agreed optimisations, follow the identical commands in the protocol
to capture `after-1.json` and `after-2.json`. Compare both pairs and inspect the
raw call counts alongside timing changes. No after measurements exist yet.
