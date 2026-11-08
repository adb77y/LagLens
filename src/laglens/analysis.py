"""Pure analysis functions. Units are milliseconds; unknown readings stay None.

Findings describe correlations, not guaranteed causes. See docs/METHODOLOGY.md.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def percentile(values, fraction):
    if not values:
        return None
    values = sorted(values)
    index = (len(values) - 1) * fraction
    low, high = math.floor(index), math.ceil(index)
    return values[low] + (values[high] - values[low]) * (index - low)


def timeline(frames, limit=500):
    """Max-per-time-bin downsampling preserves brief spikes, not just averages."""
    if len(frames) <= limit:
        return frames
    start, end = frames[0]['t'], frames[-1]['t']
    width = max((end - start) / limit, 1)
    buckets = defaultdict(list)
    for frame in frames:
        buckets[min(int((frame['t'] - start) / width), limit - 1)].append(frame)
    return [max(bucket, key=lambda frame: frame['ms']) for bucket in buckets.values()]


def analyze(frames, sensors=None, target_fps=60):
    frames = [f for f in frames if number(f.get('ms')) is not None and 0 < f['ms'] <= 60000]
    frames = sorted(frames, key=lambda f: f['t'])
    sensors = sensors or []
    if not frames:
        return {'frame_count': 0, 'average_fps': None, 'low_1_fps': None,
                'p99_ms': None, 'median_ms': None, 'stutter_count': 0,
                'stutter_rate': None, 'events': [], 'findings': [],
                'duration_s': 0, 'threshold_ms': None, 'timeline': []}
    times = [f['ms'] for f in frames]
    median = statistics.median(times)
    # A frame must exceed BOTH twice the target budget and 2.5x the run median.
    threshold = max(1000 / target_fps * 2, median * 2.5)
    events = []
    for frame in frames:
        if frame['ms'] <= threshold:
            continue
        if events and frame['t'] - events[-1]['end_ms'] <= 150:
            events[-1]['end_ms'] = frame['t']
            events[-1]['peak_ms'] = max(frame['ms'], events[-1]['peak_ms'])
            events[-1]['frames'] += 1
        else:
            events.append({'t': frame['t'], 'end_ms': frame['t'],
                           'peak_ms': frame['ms'], 'frames': 1})
    duration = sum(times) / 1000
    slowest = sorted(times, reverse=True)[:max(1, math.ceil(len(times) * .01))]
    findings = []
    long_frames = [f for f in frames if f['ms'] > threshold]
    gpu_observed = [f for f in long_frames if number(f.get('gpu_ms')) is not None]
    if len(gpu_observed) >= 5:
        high_ratio = sum(f['gpu_ms'] / f['ms'] >= .85 for f in gpu_observed) / len(gpu_observed)
        if high_ratio >= .7:
            findings.append({'title': 'GPU work overlaps the slow frames', 'confidence': 'Moderate',
                'evidence': f'GPU busy time reached at least 85% of frame time on {high_ratio:.0%} of the {len(gpu_observed)} measured slow frames.',
                'next': 'Repeat the same scene with a lower render scale or lighter GPU settings.',
                'kind': 'gpu'})
    aligned = [s for s in sensors if any(abs(s['t'] - e['t']) <= 1000 for e in events)]
    if len(aligned) >= 3:
        gpu_samples=[s for s in aligned if number(s.get('gpu_pct')) is not None]
        high_gpu=[s for s in gpu_samples if s['gpu_pct']>=95]
        if len(gpu_samples)>=3 and len(high_gpu)/len(gpu_samples)>=.5:
            findings.append({'title':'A busy GPU engine coincides with stutters','confidence':'Low',
                'evidence':f'The selected process’s busiest 3D engine reached 95% in {len(high_gpu)} nearby samples. This is sampled utilization, not per-frame GPU timing.',
                'next':'Repeat the scene with a lower render scale. Compare matched captures to test whether GPU load is involved.',
                'kind':'gpu-utilization'})
        pressure = [s for s in aligned if (s.get('ram_pct') or 0) >= 90]
        if len(pressure) / len(aligned) >= .5:
            findings.append({'title': 'Memory pressure coincides with stutters', 'confidence': 'Moderate',
                'evidence': f'System RAM was at least 90% used in {len(pressure)} of {len(aligned)} nearby samples. Paging was not measured.',
                'next': 'Close one memory-heavy background app, then capture the same scene again.',
                'kind': 'memory'})
        busy = [s for s in aligned if (s.get('cpu_peak_pct') or 0) >= 95]
        if len(busy) / len(aligned) >= .5:
            findings.append({'title': 'A busy CPU core coincides with stutters', 'confidence': 'Low',
                'evidence': f'At least one logical core reached 95% usage in {len(busy)} nearby samples. This is system-wide, not game-thread attribution.',
                'next': 'Check background CPU activity and repeat the same scene. A busy core alone does not prove the cause.',
                'kind': 'cpu'})
    ping_all = [s['ping_ms'] for s in sensors if number(s.get('ping_ms')) is not None]
    if len(ping_all) >= 10 and len(aligned) >= 3:
        baseline = statistics.median(ping_all)
        bad = [s for s in aligned if s.get('ping_lost') or
               (number(s.get('ping_ms')) is not None and s['ping_ms'] > max(80, baseline * 3))]
        if len(bad) >= 2:
            findings.append({'title': 'Probe latency rises near the stutters', 'confidence': 'Low',
                'evidence': f'{len(bad)} nearby probes timed out or exceeded 3× the run median and 80 ms. The probe is not the game server.',
                'next': 'Compare a wired connection or a quiet network. This correlation does not establish a rendering cause.',
                'kind': 'network'})
    if events and not findings:
        findings.append({'title': 'Stutters confirmed; cause unresolved', 'confidence': 'Unresolved',
            'evidence': f'{len(events)} events exceeded {threshold:.1f} ms. Available sensors do not isolate the cause.',
            'next': 'Repeat the same scene, change one setting, and compare. Shader compilation, loading and scheduling are not directly measured.',
            'kind': 'unknown'})
    elif not events:
        findings.append({'title': 'No stutters crossed this threshold', 'confidence': 'Measured',
            'evidence': f'No frame exceeded {threshold:.1f} ms in this capture. This does not measure every kind of perceived lag.',
            'next': 'Capture a scene where the problem is reproducible.', 'kind': 'clear'})
    return {'frame_count': len(frames), 'duration_s': round(duration, 3),
            'average_fps': round(1000 * len(times) / sum(times), 2),
            'low_1_fps': round(1000 / statistics.mean(slowest), 2),
            'median_ms': round(median, 3), 'p99_ms': round(percentile(times, .99), 3),
            'threshold_ms': round(threshold, 3), 'stutter_count': len(events),
            'stutter_rate': round(len(events) / max(duration / 60, .0001), 3),
            'events': events, 'findings': findings, 'timeline': timeline(frames)}


def compare(before, after):
    a, b = before['analysis'], after['analysis']
    if not a['frame_count'] or not b['frame_count']:
        raise ValueError('Both captures need frame data.')
    warnings = []
    if before.get('process_name') != after.get('process_name'):
        warnings.append('Different applications: this is not a controlled comparison.')
    if before.get('target_fps') != after.get('target_fps'):
        warnings.append('Different FPS targets: stutter thresholds are not directly comparable.')
    if min(a['duration_s'], b['duration_s']) / max(a['duration_s'], b['duration_s']) < .8:
        warnings.append('Capture durations differ by more than 20%. Compare the same scene and route.')
    if min(a['frame_count'], b['frame_count']) < 300:
        warnings.append('Short capture: fewer than 300 frames in at least one run.')
    if before.get('source') == 'demo' or after.get('source') == 'demo':
        warnings.append('Illustrative sample data. This is not a hardware benchmark.')
    metrics = []
    for key, label, unit, higher in [('average_fps', 'Average FPS', 'fps', True),
            ('low_1_fps', '1% low FPS', 'fps', True), ('p99_ms', 'P99 frame time', 'ms', False),
            ('stutter_rate', 'Stutters per minute', '/min', False)]:
        x, y = a[key], b[key]
        delta = round(y - x, 3)
        percent = round(delta / x * 100, 1) if x else None
        metrics.append({'key': key, 'label': label, 'unit': unit, 'before': x, 'after': y,
                        'delta': delta, 'percent': percent,
                        'direction': 'same' if abs(delta) < .001 else
                        ('better' if (delta > 0) == higher else 'worse')})
    return {'metrics': metrics, 'warnings': warnings,
            'statement': 'Observed differences between these two runs; repeat matched runs to establish a reliable improvement.'}
