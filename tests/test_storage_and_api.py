import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch
from pathlib import Path

from laglens.capture import CaptureManager
from laglens.reports import html_report,svg_report
from laglens.server import make_server


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.manager=CaptureManager(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_roundtrip_import(self):
        record=self.manager.import_csv('Application,FrameTime\ngame.exe,16\ngame.exe,80\n','My capture',60)
        self.assertEqual(self.manager.get(record['id'])['analysis']['frame_count'],2)
        self.assertEqual(len(self.manager.list_records()),1)

    def test_id_cannot_traverse_directory(self):
        with self.assertRaises(ValueError):self.manager.get('../secrets')

    def test_exports_escape_untrusted_capture_names(self):
        record=self.manager.samples()[0]
        record['name']='<script>alert(1)</script>'
        self.assertNotIn('<script>',html_report(record))
        self.assertIn('&lt;script&gt;',svg_report(record))

    def test_samples_always_label_their_source(self):
        self.assertTrue(all(r['source']=='demo' for r in self.manager.samples()))
        self.assertEqual(len(self.manager.samples()),2)

    def test_incident_waits_for_delayed_recovery_frames(self):
        manager=self.manager
        manager.current={'process_name':'fixture.exe','target_fps':60}
        manager._clock_start=0
        manager.groups['test']=[{'t':t,'ms':16} for t in range(1000,8001,16)]
        manager.markers=[{'t':4000,'saved_id':None,'state':'Waiting'}]
        with patch('laglens.capture.time.perf_counter',return_value=9.5):
            manager._complete_markers()
            self.assertIsNone(manager.markers[0]['saved_id'])
            manager.groups['test'].append({'t':9000,'ms':16})
            manager._complete_markers()
        self.assertIsNotNone(manager.markers[0]['saved_id'])
        self.assertEqual(len(manager.list_records()),1)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        ui=Path(__file__).parents[1]/'src/laglens/ui'
        self.server=make_server(CaptureManager(self.temp.name),ui)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
        self.temp.cleanup()

    def test_write_requires_launch_token(self):
        request=urllib.request.Request(self.url+'/api/demo',data=b'{}',headers={'Content-Type':'application/json'})
        with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request)
        self.assertEqual(error.exception.code,403)

    def test_wrong_host_rejected(self):
        request=urllib.request.Request(self.url+'/api/status',headers={'Host':'evil.invalid'})
        with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request)
        self.assertEqual(error.exception.code,403)

    def test_first_run_is_empty_not_fabricated(self):
        data=json.load(urllib.request.urlopen(self.url+'/api/sessions'))
        self.assertEqual(data,[])

    def test_path_traversal_cannot_read_project_files(self):
        with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(self.url+'/../pyproject.toml')


if __name__=='__main__':unittest.main()
