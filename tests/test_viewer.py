"""Regression checks for evidence honesty and retention. No Azure calls are made."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("viewer_server", ROOT / "demo-viewer/server.py")
viewer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = viewer
spec.loader.exec_module(viewer)
try:
    import azure.core.exceptions
    import docops.azure_io
    HAS_AZURE = True
except ImportError:
    HAS_AZURE = False

class ViewerTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.patch = patch.object(viewer, "RUN_ROOT", Path(folder.name))
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def run_record(self, **kwargs):
        return viewer.DemoRun(id="a" * 32, mode=kwargs.pop("mode", "azure"),
                              request_id="docops-test-001", **kwargs)

    def fake_store(self, status="completed", **report_changes):
        state = dict(schema_version=1, request_id="docops-test-001", repository_id="docs-fixture-v1",
                     status=status, actions=["check_links", "check_translation_drift"])
        report = json.loads((ROOT / "samples/expected-report.json").read_text())
        report.update(request_id=state["request_id"], **report_changes)
        props = SimpleNamespace(etag="etag-test", last_modified=datetime(2026, 10, 2, tzinfo=timezone.utc))
        store = MagicMock()
        store.state_blob.return_value.download_blob.return_value = SimpleNamespace(
            readall=lambda: json.dumps(state).encode(), properties=props)
        store.container.download_blob.return_value = SimpleNamespace(
            readall=lambda: json.dumps(report).encode(), properties=props)
        store.container.container_name = "docops-results"
        store.container.get_blob_client.return_value.url = "https://example.blob.core.windows.net/report.json"
        return store

    def test_observer_error_never_claims_job_failure(self):
        run = self.run_record()
        viewer.update_stage(run, "job", "running", "Observing", "Reader")
        viewer.fail_run(run, ImportError("azure.storage.queue"), observation=True)
        self.assertEqual(run.status, "observation_error")
        self.assertEqual(run.stages[4]["status"], "unverified")
        self.assertIn("do not dispatch again", run.recovery)
        self.assertEqual(viewer.get_run(run.id)["error"], run.error)

    def test_interrupted_observation_is_recoverable_after_restart(self):
        run = self.run_record()
        viewer.update_stage(run, "job", "running", "Observing worker", "Viewer")
        viewer.persist(run)
        restored = viewer.get_run(run.id)
        self.assertEqual(restored["status"], "observation_error")
        self.assertEqual(restored["stages"][4]["status"], "unverified")
        self.assertIn("without dispatching", restored["recovery"])
        self.assertEqual(restored["request_id"], run.request_id)

    def test_missing_storage_dependency_is_in_preflight(self):
        def fake_import(name):
            if name == "azure.storage.queue":
                raise ImportError(name)
        with patch.object(viewer.importlib, "import_module", side_effect=fake_import):
            available, reason = viewer.azure_available()
        self.assertFalse(available)
        self.assertIn("azure.storage.queue", reason)

    def test_unavailable_observer_does_not_dispatch(self):
        run = self.run_record()
        with patch.object(viewer, "azure_available", return_value=(False, "missing dependency")):
            viewer.run_azure(run)
        self.assertEqual(run.status, "observation_error")
        self.assertNotIn("dispatch_receipt", run.evidence)
        self.assertEqual(run.stages[0]["status"], "waiting")

    def test_local_keeps_actual_artifacts(self):
        run = self.run_record(mode="local")
        viewer.run_local(run)
        self.assertEqual(run.status, "completed", run.error)
        self.assertEqual(run.report["finding_count"], 2)
        self.assertEqual(run.stages[0]["status"], "simulated")
        self.assertEqual(run.stages[1]["status"], "simulated")
        path = Path(run.evidence["report_path"])
        self.assertTrue(Path(run.evidence["queue_path"]).exists())
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), run.evidence["report_sha256"])
        self.assertEqual(json.loads(path.read_text())["request_id"], run.request_id)

    def test_recording_retains_original_timestamps_without_delays(self):
        run = self.run_record(mode="replay")
        run.request_id = "docops-both-001"
        with patch.object(viewer.time, "sleep", side_effect=AssertionError("No artificial delays")):
            viewer.run_replay(run)
        self.assertEqual(run.status, "completed", run.error)
        logs = [e for e in run.events if e["source"] == "Recorded Azure console log"]
        self.assertEqual(len(logs), 2)
        self.assertTrue(all(e["timestamp"].startswith("2026-09-30") for e in logs))
        self.assertEqual(run.stages[1]["status"], "inferred")
        self.assertEqual(run.stages[4]["status"], "recorded")

    def portal_record(self):
        return dict(mode='azure', status='completed', request_id='docops-test-001',
                    report={'request_id': 'docops-test-001'}, evidence={
                        'blob_path': 'docops-results/reports/docops-test-001/report.json',
                        'blob_url': 'https://example.blob.core.windows.net/docops-results/reports/docops-test-001/report.json'})

    def portal_config(self):
        return patch.dict(viewer.os.environ, {'AZURE_STORAGE_RESOURCE_ID':
            '/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/demo/providers/Microsoft.Storage/storageAccounts/example'})

    def test_portal_link_matches_observed_account_and_request(self):
        with self.portal_config():
            source = viewer.azure_portal_source(self.portal_record())
        self.assertTrue(source['url'].startswith('https://portal.azure.com/#view/'))
        self.assertIn('/storageAccounts/example/path/docops-results', unquote(source['url']))
        self.assertEqual(source['report_path'], 'reports/docops-test-001/report.json')

    def test_portal_link_rejects_unrelated_or_credentialed_sources(self):
        changes = [
            {'blob_url': 'https://otheraccount.blob.core.windows.net/docops-results/reports/docops-test-001/report.json'},
            {'blob_url': 'https://example.blob.core.windows.net/docops-results/reports/docops-other/report.json'},
            {'blob_url': self.portal_record()['evidence']['blob_url'] + '?sig=private'},
            {'blob_url': self.portal_record()['evidence']['blob_url'] + '#fragment'},
            {'blob_path': 'other-container/reports/docops-test-001/report.json'},
            {'blob_url': 'https://example.blob.core.windows.net.attacker.invalid/report.json'},
        ]
        with self.portal_config():
            for change in changes:
                with self.subTest(change=change):
                    data = self.portal_record()
                    data['evidence'].update(change)
                    self.assertIsNone(viewer.azure_portal_source(data)['url'])

    def test_restoring_or_changing_modes_cannot_reuse_stale_portal_link(self):
        with self.portal_config():
            for mode, status in [('local', 'completed'), ('replay', 'completed'), ('azure', 'running')]:
                with self.subTest(mode=mode, status=status):
                    data = self.portal_record()
                    data.update(mode=mode, status=status, stages=[], azure_source={'url': 'https://stale.invalid/'})
                    self.assertIsNone(viewer.recovered_snapshot(data)['azure_source']['url'])
        with patch.dict(viewer.os.environ, {'AZURE_STORAGE_RESOURCE_ID': ''}):
            self.assertIsNone(viewer.azure_portal_source(self.portal_record())['url'])

    @unittest.skipUnless(HAS_AZURE, "Optional Azure SDK not installed")
    def test_accepted_state_does_not_prove_queue_delivery(self):
        run = self.run_record()
        store = self.fake_store(status="accepted")
        self.assertFalse(viewer.observe_store(run, store))
        self.assertEqual(run.stages[3]["status"], "unverified")
        self.assertIsNone(run.report)
        store.container.download_blob.assert_not_called()

    @unittest.skipUnless(HAS_AZURE, "Optional Azure SDK not installed")
    def test_report_must_match_repository_and_actions(self):
        run = self.run_record()
        with self.assertRaises(ValueError):
            viewer.observe_store(run, self.fake_store(repository_id="other-repo"))
        self.assertIsNone(run.report)

    @unittest.skipUnless(HAS_AZURE, "Optional Azure SDK not installed")
    def test_existing_lookup_never_instantiates_a_foundry_client(self):
        run = self.run_record(monitor_only=True)
        with patch.object(viewer, "azure_available", return_value=(True, "Ready")), \
             patch("docops.azure_io.AzureStore", return_value=self.fake_store()), \
             patch("azure.ai.projects.AIProjectClient", side_effect=AssertionError("No dispatch allowed")):
            viewer.run_azure(run)
        self.assertEqual(run.status, "completed", run.error)
        self.assertEqual(run.stages[4]["status"], "inferred")
        self.assertNotIn("dispatch_receipt", run.evidence)
        self.assertIn("Not captured", run.evidence["job_execution"])

if __name__ == "__main__":
    unittest.main()
