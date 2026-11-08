"""Windows capture adapter. Only the selected PID and our own ETW session are used."""
from __future__ import annotations

import csv
import ctypes
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from collections import defaultdict
from pathlib import Path

import psutil

from .analysis import analyze
from .importer import normalize, read_csv
from .gpu import GpuSampler

PRESENTMON_SHA256 = 'b2a706bc6ad475749e3b7e3409263aa1e6906d45bdcf993f6dbc0f660188f1af'
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def resource_root():
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


def is_admin():
    return bool(os.name == 'nt' and ctypes.windll.shell32.IsUserAnAdmin())


def processes():
    result = []
    for p in psutil.process_iter(['pid', 'name', 'memory_info']):
        try:
            if p.pid < 5 or not p.info['name']:
                continue
            memory = p.info['memory_info'].rss if p.info['memory_info'] else 0
            result.append({'pid': p.pid, 'name': p.info['name'], 'memory_mb': round(memory / 1048576)})
        except (psutil.Error, OSError):
            continue
    return sorted(result, key=lambda item: (-item['memory_mb'], item['name'].lower()))


def ping_probe():
    result = subprocess.run(['ping', '-n', '1', '-w', '600', '1.1.1.1'],
                            capture_output=True, creationflags=NO_WINDOW, timeout=2)
    text = result.stdout.decode(errors='replace')
    match = re.search(r'[=<]\s*(\d+)\s*ms', text, re.IGNORECASE)
    return (float(match.group(1)) if match else None), result.returncode != 0


class CaptureManager:
    def __init__(self, data_dir):
        self.directory = Path(data_dir)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.current = None
        self.groups = defaultdict(list)
        self.sensors = []
        self.markers = []
        self.worker = None
        self.reader = None
        self.sensor_thread = None
        self.event = threading.Event()
        self.error = None
        self.hotkey_ready = False
        self.hotkey_note = 'Available during a live capture on Windows.'
        self._hotkey_thread_id = None
        self._wall_start = 0
        self._clock_start = 0
        self._session_name = ''
        self._target_fps = 60

    def vendor(self):
        return resource_root() / 'vendor' / 'PresentMon.exe'

    def capabilities(self):
        vendor = self.vendor()
        return {'windows': os.name == 'nt', 'admin': is_admin(),
                'presentmon': vendor.is_file(), 'presentmon_version': '2.6.0',
                'hotkey_ready': self.hotkey_ready, 'hotkey_note': self.hotkey_note,
                'network_target': '1.1.1.1 (ICMP probe, not your game server)'}

    def _save(self, record):
        path = self.directory / (record['id'] + '.json')
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(record, allow_nan=False, separators=(',', ':')), encoding='utf-8')
        temporary.replace(path)

    def _record(self, name, source, frames, sensors=None, target=60, **extra):
        record = {'id': uuid.uuid4().hex, 'name': name[:120], 'source': source,
                  'process_name': extra.pop('process_name', name),
                  'created_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                  'target_fps': target, 'frames': frames, 'sensors': sensors or [], **extra}
        record['analysis'] = analyze(frames, record['sensors'], target)
        self._save(record)
        return record

    def list_records(self):
        result = []
        for path in self.directory.glob('*.json'):
            try:
                record = json.loads(path.read_text(encoding='utf-8'))
                result.append({k: record.get(k) for k in
                               ['id', 'name', 'source', 'process_name', 'created_at', 'analysis', 'target_fps']})
                result[-1]['analysis'] = {k: v for k, v in result[-1]['analysis'].items()
                                          if k not in ('timeline', 'events', 'findings')}
            except (OSError, ValueError, KeyError):
                continue
        return sorted(result, key=lambda row: row['created_at'] or '', reverse=True)

    def get(self, record_id):
        if not re.fullmatch('[a-f0-9]{32}', record_id):
            raise ValueError('Invalid capture ID.')
        path = self.directory / (record_id + '.json')
        if not path.is_file():
            raise ValueError('Capture not found.')
        return json.loads(path.read_text(encoding='utf-8'))

    def import_csv(self, text, name, target):
        frames, process, group_count = read_csv(text)
        return self._record(name or process, 'import', frames, target=target,
                            process_name=process, swapchains_in_file=group_count,
                            notes='Dominant process/swap chain selected. Hardware and network samples were not imported.')

    def samples(self):
        """Explicitly synthetic examples, never presented as measurements of this PC."""
        existing = [r for r in self.list_records() if r['source'] == 'demo']
        if len(existing) >= 2:
            return existing[:2]
        result = []
        for name, improved in [('Sample — original settings', False), ('Sample — adjusted settings', True)]:
            frames, sensors, t = [], [], 0
            for i in range(3600):
                ms = 15.5 + 1.2 * __import__('math').sin(i * .19)
                if i % (1150 if improved else 340) == 170:
                    ms = 58 if improved else 148
                t += ms
                frames.append({'t': round(t, 3), 'ms': round(ms, 3),
                               'gpu_ms': round(ms * .43, 3), 'cpu_ms': round(ms * .62, 3)})
                if i % 60 == 0:
                    sensors.append({'t': t, 'cpu_pct': 32, 'cpu_peak_pct': 68,
                                    'ram_pct': 46, 'process_ram_mb': 4100,
                                    'ping_ms': None, 'ping_lost': None})
            result.append(self._record(name, 'demo', frames, sensors,
                                      process_name='Illustrative game',
                                      notes='Synthetic example. Not a benchmark or a measurement of your hardware.'))
        return result

    def start(self, pid, target=60, duration=120, probe=False):
        if os.name != 'nt':
            raise ValueError('Live recording requires Windows. CSV import works on other platforms.')
        if not isinstance(pid, int) or pid <= 4:
            raise ValueError('Select a running game first.')
        if target not in (30, 60, 90, 120, 144, 165, 240):
            raise ValueError('Unsupported FPS target.')
        if not isinstance(duration, int) or not 10 <= duration <= 600:
            raise ValueError('Capture duration must be 10–600 seconds.')
        vendor = self.vendor()
        if not vendor.is_file():
            raise ValueError('PresentMon is missing. Run scripts/fetch_vendor.py or use the portable release.')
        if hashlib.sha256(vendor.read_bytes()).hexdigest() != PRESENTMON_SHA256:
            raise ValueError('PresentMon verification failed. Re-download the official pinned version.')
        try:
            process = psutil.Process(pid)
            process_name = process.name()
        except psutil.Error as error:
            raise ValueError('This process has exited. Refresh the process list.') from error
        with self.lock:
            if self.current:
                raise ValueError('A recording is already running.')
            self.groups = defaultdict(list)
            self.sensors, self.markers, self.error = [], [], None
            self.event = threading.Event()
            self._wall_start, self._clock_start = time.time(), time.perf_counter()
            self._session_name = 'LagLens-' + uuid.uuid4().hex[:12]
            self._target_fps = target
            self.current = {'id': uuid.uuid4().hex, 'process_name': process_name,
                            'pid': pid, 'target_fps': target, 'duration_limit': duration,
                            'probe': bool(probe), 'started_at': self._wall_start}
            command = [str(vendor), '--process_id', str(pid), '--output_stdout',
                       '--no_console_stats', '--v2_metrics', '--no_track_input',
                       '--no_track_display', '--no_track_gpu',
                       '--session_name', self._session_name, '--timed', str(duration),
                       '--terminate_after_timed', '--terminate_on_proc_exit']
            self.worker = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                           text=True, encoding='utf-8', errors='replace',
                                           creationflags=NO_WINDOW, bufsize=1)
            self.reader = threading.Thread(target=self._read, daemon=True)
            self.sensor_thread = threading.Thread(target=self._sensors, args=(process,), daemon=True)
            self.reader.start()
            self.sensor_thread.start()
            threading.Thread(target=self._hotkey, daemon=True).start()
        return self.snapshot()

    def _read(self):
        worker = self.worker
        previous = {}
        try:
            for row in csv.DictReader(worker.stdout):
                key = row.get('SwapChainAddress', 'main')
                frame, timestamp = normalize(row, previous.get(key))
                if timestamp is not None:
                    previous[key] = timestamp
                if frame:
                    with self.lock:
                        self.groups[key].append(frame)
            worker.wait(timeout=5)
            error = worker.stderr.read().strip()
            if worker.returncode and error:
                self.error = error[-1600:]
        except Exception as error:
            self.error = str(error)
        finally:
            self._finish()

    def _sensors(self, process):
        stop_event=self.event
        probe=bool(self.current and self.current['probe'])
        gpu=GpuSampler(process.pid)
        psutil.cpu_percent(percpu=True)
        while not stop_event.wait(.5):
            try:
                cores = psutil.cpu_percent(percpu=True)
                memory = psutil.virtual_memory()
                sample = {'t': (time.perf_counter() - self._clock_start) * 1000,
                          'cpu_pct': sum(cores) / len(cores), 'cpu_peak_pct': max(cores),
                          'ram_pct': memory.percent,
                          'gpu_pct': gpu.sample(),
                          'process_ram_mb': round(process.memory_info().rss / 1048576, 1),
                          'ping_ms': None, 'ping_lost': None}
                if probe:
                    sample['ping_ms'], sample['ping_lost'] = ping_probe()
                with self.lock:
                    self.sensors.append(sample)
                    self._complete_markers()
            except (psutil.Error, OSError, subprocess.SubprocessError):
                continue
        gpu.close()

    def _frames(self):
        if not self.groups:
            return []
        return list(max(self.groups.values(), key=len))

    def _hotkey(self):
        # Register one shortcut, not a keyboard recorder or a game hook.
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        self._hotkey_thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        if not user32.RegisterHotKey(None, 1, 0x4000 | 0x0001 | 0x0002, 0x77):
            self.hotkey_note = 'Ctrl+Alt+F8 is in use. Use the Mark stutter button.'
            return
        self.hotkey_ready = True
        self.hotkey_note = 'Ctrl+Alt+F8 marks the previous 30 seconds and the following 5 seconds.'
        message = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                if message.message == 0x0312 and self.current:
                    self.mark()
        finally:
            user32.UnregisterHotKey(None, 1)
            self.hotkey_ready = False

    def mark(self):
        with self.lock:
            if not self.current:
                raise ValueError('Start a recording before marking a stutter.')
            if len(self.markers) >= 20:
                raise ValueError('This recording already has 20 markers.')
            marker = {'t': (time.perf_counter() - self._clock_start) * 1000,
                      'saved_id': None, 'state': 'Collecting 5 seconds after the marker'}
            self.markers.append(marker)
            return dict(marker)

    def _complete_markers(self, force=False):
        now = (time.perf_counter() - self._clock_start) * 1000
        available_frames=self._frames()
        for index, marker in enumerate(self.markers):
            if marker['saved_id'] or (not force and now < marker['t'] + 5000):
                continue
            if not force and now<marker['t']+10000 and (not available_frames or available_frames[-1]['t']<marker['t']+5000):
                marker['state']='Waiting for delayed frame delivery'
                continue
            frames = [f.copy() for f in available_frames if max(0, marker['t']-30000) <= f['t'] <= marker['t']+5000]
            if not frames:
                marker['state'] = 'No frames in this window'
                continue
            sensors = [s.copy() for s in self.sensors if frames[0]['t'] <= s['t'] <= frames[-1]['t']]
            start = frames[0]['t']
            for frame in frames:
                frame['t'] -= start
            for sensor in sensors:
                sensor['t'] -= start
            record = self._record(f"{self.current['process_name']} — marked stutter {index+1}",
                 'incident', frames, sensors, self.current['target_fps'],
                 process_name=self.current['process_name'], marker_ms=marker['t']-start,
                 notes='Up to 30 seconds before the marker, plus up to 5 seconds after.')
            marker.update(saved_id=record['id'], state='Saved')

    def _finish(self):
        self.event.set()
        with self.lock:
            if not self.current:
                return
            self._complete_markers(force=True)
            frames = self._frames()
            current = self.current
            if frames:
                self._record(current['process_name'] + ' — full capture', 'live', frames,
                    list(self.sensors), current['target_fps'], process_name=current['process_name'],
                    notes='Light capture: presented frame intervals from the dominant swap chain. Display completion and per-frame GPU timings are disabled for reliable frame delivery. GPU utilization is sampled separately through Windows counters. System samples are approximately aligned to capture start.')
            elif not self.error:
                self.error = 'No frames received. Select the rendering process and play in its window. If capture access is denied, restart LagLens as administrator.'
            self.current = None
            if self._hotkey_thread_id and os.name == 'nt':
                ctypes.windll.user32.PostThreadMessageW(self._hotkey_thread_id, 0x0012, 0, 0)

    def stop(self):
        with self.lock:
            if not self.current:
                return self.snapshot()
            worker, session = self.worker, self._session_name
        if worker and worker.poll() is None:
            try:
                subprocess.run([str(self.vendor()), '--session_name', session,
                                '--terminate_existing_session'], timeout=5,
                               capture_output=True, creationflags=NO_WINDOW)
                worker.wait(timeout=5)
            except subprocess.TimeoutExpired:
                worker.terminate()  # Only our own child, never the game.
        if self.reader and threading.current_thread() != self.reader:
            self.reader.join(timeout=8)
        self._finish()
        return self.snapshot()

    def snapshot(self):
        with self.lock:
            current = dict(self.current) if self.current else None
            frames = self._frames()
            if current:
                current['elapsed_s'] = round(time.perf_counter() - self._clock_start, 1)
            return {'capture': current, 'analysis': analyze(frames[-30000:], self.sensors[-120:],
                    self._target_fps),
                    'latest_sensor': self.sensors[-1] if self.sensors else None,
                    'markers': [dict(m) for m in self.markers], 'error': self.error,
                    'capabilities': self.capabilities()}
