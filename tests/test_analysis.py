import unittest
from laglens.analysis import analyze, compare, timeline
from laglens.importer import read_csv


def frames(times, gpu=None):
    t, result = 0, []
    for ms in times:
        t += ms
        result.append({'t': t, 'ms': ms, 'gpu_ms': gpu})
    return result


class AnalysisTests(unittest.TestCase):
    def test_constant_60_fps(self):
        result = analyze(frames([1000/60] * 600))
        self.assertAlmostEqual(result['average_fps'], 60)
        self.assertAlmostEqual(result['low_1_fps'], 60)
        self.assertEqual(result['stutter_count'], 0)

    def test_short_hitch_survives_downsample(self):
        data = frames([16] * 1000 + [180] + [16] * 1000)
        self.assertEqual(max(f['ms'] for f in timeline(data, 40)), 180)
        self.assertEqual(analyze(data)['stutter_count'], 1)
        self.assertEqual(analyze(data)['findings'][0]['confidence'], 'Unresolved')

    def test_consecutive_spikes_group_into_one_event(self):
        result = analyze(frames([16] * 100 + [80, 90] + [16] * 100))
        self.assertEqual(result['stutter_count'], 1)
        self.assertEqual(result['events'][0]['frames'], 2)

    def test_invalid_samples_do_not_become_zero(self):
        result = analyze([{'t': 0, 'ms': float('nan')}, {'t': 1, 'ms': -1}])
        self.assertIsNone(result['average_fps'])

    def test_low_1_uses_mean_of_slowest_frames(self):
        result = analyze(frames([10] * 198 + [50, 100]))
        self.assertAlmostEqual(result['low_1_fps'], 1000/75, places=2)

    def test_comparison_normalizes_stutters_by_time(self):
        a = {'analysis': analyze(frames([16]*600 + [100])), 'target_fps': 60}
        b = {'analysis': analyze(frames([16]*1200 + [100])), 'target_fps': 60}
        result = compare(a, b)
        rate = result['metrics'][-1]
        self.assertEqual(rate['direction'], 'better')
        self.assertTrue(result['warnings'])

    def test_zero_baseline_has_no_percentage(self):
        a = {'analysis': analyze(frames([16]*600)), 'target_fps': 60}
        b = {'analysis': analyze(frames([16]*600+[100])), 'target_fps': 60}
        self.assertIsNone(compare(a, b)['metrics'][-1]['percent'])

    def test_gpu_evidence_requires_measured_busy_time(self):
        data = frames(([16]*20+[80])*7)
        self.assertEqual(analyze(data)['findings'][0]['kind'], 'unknown')
        for f in data:
            f['gpu_ms'] = f['ms']*.95
        self.assertEqual(analyze(data)['findings'][0]['kind'], 'gpu')

    def test_import_separates_swapchains(self):
        text = 'Application,ProcessID,SwapChainAddress,CPUStartTime,FrameTime\n'
        text += '\n'.join(f'game.exe,1,A,{i*16},16\ngame.exe,1,B,{i*16+1},200' for i in range(20))
        data, name, count = read_csv(text)
        self.assertEqual(count, 2)
        self.assertEqual(len(data), 20)
        self.assertEqual(name, 'game.exe')
        self.assertEqual(analyze(data)['average_fps'], 62.5)

    def test_v1_seconds_and_missing_gpu(self):
        data, _, _ = read_csv('Application,TimeInSeconds,MsBetweenPresents\ngame.exe,1,16\ngame.exe,1.016,16\n')
        self.assertAlmostEqual(data[1]['t'], 16)
        self.assertIsNone(data[0]['gpu_ms'])

    def test_unknown_format_rejected(self):
        with self.assertRaises(ValueError):
            read_csv('foo,bar\n1,2')

    def test_frame_time_only_csv_gets_cumulative_timestamps(self):
        data,_,_=read_csv('Application,FrameTime\ngame.exe,16\ngame.exe,20\ngame.exe,80\n')
        self.assertEqual([f['t'] for f in data],[0,20,100])

    def test_na_gpu_is_not_zero(self):
        data,_,_=read_csv('Application,FrameTime,GPUBusy\ngame.exe,16,NA\n')
        self.assertIsNone(data[0]['gpu_ms'])


if __name__ == '__main__':
    unittest.main()
