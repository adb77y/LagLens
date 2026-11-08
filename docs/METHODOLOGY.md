# Measurement and interpretation

## Frame source

PresentMon 2.6.0 collects ETW events for one explicitly selected PID in a uniquely named LagLens session. The light capture mode uses `--v2_metrics --no_track_display --no_track_gpu --no_track_input`.

Display-completion tracking was observed to stop delivering complete frame rows in a controlled Direct3D fixture on the development machine. Light capture delivered the full stream. Therefore this version disables display completion and per-frame GPU tracking; it does not silently treat missing GPU times as zero. Imported CSVs can still include per-frame GPU busy times.

This measures intervals between application presents. It does not prove that every frame was displayed or identify native versus generated frames. It does not measure click-to-photon latency, shader compilation or thermal throttling.

Multiple swap chains are stored separately. The dominant chain by frame count is selected for analysis. A game that changes swap chains mid-recording can therefore have an incomplete analyzed segment. This selection is preferable to falsely merging simultaneous chains, but remains a known limitation.

## System context

- CPU and RAM are sampled approximately every 500 ms using psutil.
- `cpu_peak_pct` is the busiest system logical core, not the game's busiest thread.
- GPU utilization is the selected PID's busiest available Windows `GPU Engine` counter whose engine type is `3D`. It is not whole-device utilization or per-frame GPU duration. Child rendering processes need to be selected explicitly.
- The optional network probe sends one ICMP echo to `1.1.1.1` during each sensor iteration. Blocking probe latency reduces the sampling frequency. It is not the game's server and may be deprioritized by the network.
- PresentMon timestamps and sensor timestamps use approximately the same capture-start epoch; startup and delivery delays prevent exact causal alignment.

Unavailable sensors remain `null` and display as a dash. No temperatures, clocks, VRAM or disk paging are inferred.

## Findings

These confidence labels describe rule strength, **not calibrated statistical probabilities**:

| Finding | Rule | Confidence |
|---|---|---|
| GPU work overlaps slow frames | At least five slow frames with GPU busy data; busy/frame ratio at least 85% in at least 70% of them | Moderate |
| Busy GPU engine near stutters | At least three nearby valid GPU samples, at least half at 95% or higher | Low |
| Memory pressure near stutters | At least three nearby context samples, at least half with system RAM at 90% or higher | Moderate |
| Busy CPU core near stutters | At least three nearby samples, at least half with peak logical-core use at 95% or higher | Low |
| Probe latency rises near stutters | At least ten successful run probes, plus at least two nearby probes that time out or exceed both 80 ms and 3× the run median | Low |

Nearby means within one second of an event's first slow frame. No matching rule produces **cause unresolved**. No slow frames produces **no events crossed this threshold**, not a claim that the entire experience is lag-free.

## Comparisons

Stutter counts are normalized by measured frame-time duration into events/minute. A percentage change from a zero baseline is undefined and shown as a dash. Differences in application, target FPS, short captures and mismatched durations trigger warnings.

Use the same scene, route, warmup and FPS target; change one setting. Repeat multiple matched runs. One pair is descriptive, not statistical proof of improvement. Longer recordings, loading screens and gameplay variability can change the median and threshold, so report both alongside the comparison.

Synthetic example sessions are always labelled. They are test fixtures for learning the app, not measured hardware results.

## Sources

- [PresentMon Console Application](https://github.com/GameTechDev/PresentMon/blob/v2.6.0/README-ConsoleApplication.md)
- [Windows PdhGetFormattedCounterArrayW](https://learn.microsoft.com/en-us/windows/win32/api/pdh/nf-pdh-pdhgetformattedcounterarrayw)
- [Windows PdhAddEnglishCounterW](https://learn.microsoft.com/en-us/windows/win32/api/pdh/nf-pdh-pdhaddenglishcounterw)
