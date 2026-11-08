"""Parse real PresentMon CSV exports without inventing unavailable metrics."""
import csv
import io
from collections import defaultdict

from .analysis import number


def normalize(row, previous=None):
    clean = {str(k).strip().lstrip('\ufeff').lower(): v for k, v in row.items() if k}
    def pick(*keys):
        for key in keys:
            value = number(clean.get(key.lower()))
            if value is not None:
                return value
        return None
    t = pick('CPUStartTime', 'TimeInSeconds', 'CPUStartQPCTime')
    if 'timeinseconds' in clean and t is not None:
        t *= 1000
    ms = pick('FrameTime', 'MsBetweenPresents', 'MsBetweenAppStart', 'msBetweenPresents')
    if ms is None and previous is not None and t is not None:
        ms = t - previous
    if ms is None or ms <= 0 or ms > 60000:
        return None, t
    if t is None:
        t=(previous or 0)+ms
    return {'t': t, 'ms': ms,
            'gpu_ms': pick('GPUBusy', 'MsGPUBusy', 'msGPUActive'),
            'cpu_ms': pick('CPUBusy', 'MsCPUBusy')}, t


def read_csv(text):
    if len(text) > 32 * 1024 * 1024:
        raise ValueError('CSV is larger than 32 MB. Export a shorter capture.')
    reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    if not reader.fieldnames:
        raise ValueError('The CSV is empty.')
    # Select the dominant process/swap chain; interleaved swap chains are not FPS.
    groups = defaultdict(list)
    previous = {}
    names = {}
    for index, row in enumerate(reader):
        if index > 250000:
            raise ValueError('CSV exceeds 250,000 rows. Export a shorter capture.')
        key = (row.get('ProcessID', ''), row.get('SwapChainAddress', ''))
        frame, timestamp = normalize(row, previous.get(key))
        if timestamp is not None:
            previous[key] = timestamp
        if frame:
            groups[key].append(frame)
            names[key] = row.get('Application', 'Imported application')
    if not groups:
        raise ValueError('No valid frame times found. Use a PresentMon CSV with FrameTime, MsBetweenPresents or CPUStartTime columns.')
    key = max(groups, key=lambda item: len(groups[item]))
    frames = sorted(groups[key], key=lambda f: f['t'])
    start = frames[0]['t']
    for frame in frames:
        frame['t'] -= start
    return frames, names[key], len(groups)
