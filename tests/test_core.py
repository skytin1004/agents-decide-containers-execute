from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest

from docops.checks import FIXTURE, check_links, check_translation_drift, execute, safe_path
from docops.contracts import InvalidRequest, RequestConflict, WorkRequest
from docops.local import LocalStore


def request(**changes):
    data = {"schema_version": 1, "request_id": "docops-test-001",
            "repository_id": "docs-fixture-v1",
            "actions": ["check_links", "check_translation_drift"]}
    data.update(changes)
    return WorkRequest.parse(data)


class ContractTests(unittest.TestCase):
    def test_rejects_shell_action(self):
        with self.assertRaises(InvalidRequest): request(actions=["run_shell"])

    def test_rejects_repository_url(self):
        with self.assertRaises(InvalidRequest): request(repository_id="https://example.org/repo")

    def test_rejects_path_traversal_in_request_id(self):
        with self.assertRaises(InvalidRequest): request(request_id="docops-../../secret")

    def test_rejects_extra_fields(self):
        with self.assertRaises(InvalidRequest): request(command="rm -rf /")

    def test_rejects_boolean_schema_version(self):
        with self.assertRaises(InvalidRequest): request(schema_version=True)

    def test_rejects_duplicate_actions(self):
        with self.assertRaises(InvalidRequest): request(actions=["check_links", "check_links"])

    def test_action_order_does_not_change_identity(self):
        self.assertEqual(request().digest, request(actions=["check_translation_drift", "check_links"]).digest)


class CheckTests(unittest.TestCase):
    def test_known_fixture_finds_two_specific_defects(self):
        result = execute(request())
        self.assertEqual(result["finding_count"], 2)
        self.assertEqual(result["findings"]["check_links"][0]["file"], "docs/en/index.md")
        self.assertEqual(result["findings"]["check_links"][0]["line"], 6)
        self.assertEqual(result["findings"]["check_translation_drift"][0]["file"], "docs/ko/setup.md")

    def test_only_selected_check_runs(self):
        result = execute(request(actions=["check_links"]))
        self.assertEqual(set(result["findings"]), {"check_links"})
        self.assertEqual(result["finding_count"], 1)

    def test_links_ignore_external_urls_anchors_and_fenced_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "index.md").write_text("[web](https://invalid.example/)\n[anchor](#part)\n```md\n[x](missing.md)\n```\n[x](missing2.md)\n", encoding="utf-8")
            found = check_links(root)
            self.assertEqual([f["target"] for f in found], ["missing2.md"])

    def test_manifest_paths_cannot_escape(self):
        with self.assertRaises(ValueError): safe_path(FIXTURE, "../secret")

    def test_translation_hash_is_portable_across_crlf(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "source.md").write_bytes(b"first\r\nsecond\r\n")
            (root / "translated.md").write_text("translation", encoding="utf-8")
            (root / "translations.json").write_text(json.dumps({"translations": [{"source": "source.md", "translation": "translated.md", "source_sha256": hashlib.sha256(b"first\nsecond\n").hexdigest()}]}))
            self.assertEqual(check_translation_drift(root), [])


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = LocalStore(Path(self.tmp.name))

    def tearDown(self): self.tmp.cleanup()

    def test_no_action_does_not_queue_work(self):
        self.assertEqual(self.store.submit(request(actions=[]))["status"], "no_action")
        self.assertIsNone(self.store.get(request().request_id))

    def test_duplicate_completed_request_does_not_run_again(self):
        self.store.submit(request())
        self.store.run_one()
        self.assertEqual(self.store.submit(request())["status"], "duplicate")
        self.assertEqual(self.store.run_one()["status"], "idle")
        self.assertEqual(self.store.get(request().request_id)["attempts"], 1)

    def test_conflicting_payload_is_rejected(self):
        self.store.submit(request())
        with self.assertRaises(RequestConflict): self.store.submit(request(actions=["check_links"]))

    def test_concurrent_submissions_create_one_logical_request(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.store.submit(request()), range(16)))
        self.assertEqual(sum(r["status"] == "queued" for r in results), 1)

    def test_only_one_worker_can_claim(self):
        self.store.submit(request())
        with ThreadPoolExecutor(max_workers=8) as pool:
            claims = list(pool.map(lambda _: self.store.claim(), range(8)))
        self.assertEqual(sum(c is not None for c in claims), 1)

    def test_expired_owner_cannot_commit_after_reclaim(self):
        self.store.submit(request())
        original, old_owner = self.store.claim(now=time.time()-100)
        new_request, new_owner = self.store.claim()
        with self.assertRaises(RuntimeError): self.store.finish(original, old_owner, execute(original))
        self.store.finish(new_request, new_owner, execute(new_request))
        self.assertEqual(self.store.get(original.request_id)["status"], "completed")

    def test_failure_is_retried_and_report_can_be_reexported(self):
        self.store.submit(request())
        with self.assertRaises(RuntimeError): self.store.run_one(fail_once=True)
        self.store.run_one()
        state = self.store.get(request().request_id)
        self.assertEqual((state["status"], state["attempts"]), ("completed", 2))
        directory = self.store.export(request().request_id)
        self.assertIn("Findings: **2**", (directory / "report.md").read_text())

    def test_third_failure_moves_request_to_poison(self):
        self.store.submit(request())
        for _ in range(3):
            with self.assertRaises(RuntimeError): self.store.run_one(fail_once=True)
        self.assertEqual(self.store.get(request().request_id)["status"], "poison")
        self.assertIsNone(self.store.claim())


if __name__ == "__main__": unittest.main()
