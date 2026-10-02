import copy
import json
import unittest

from docops.checks import execute
from docops.contracts import WorkRequest
from docops.issue_publisher import (WEB, PublicationError, issue_content,
                                    publish, read_json, validate_report)


class FakeGitHub:
    def __init__(self):
        self.items = []
        self.posts = 0
        self.lose_response = False
        self.forbidden = False

    def issues(self):
        if self.forbidden:
            raise PublicationError("GitHub GET returned HTTP 403")
        return self.items

    def create(self, content):
        self.posts += 1
        issue = {**content, "number": 1, "html_url": WEB + "/issues/1",
                 "user": {"login": "github-actions[bot]"}, "state": "open"}
        self.items.append(issue)
        if self.lose_response:
            raise PublicationError("Lost POST response")
        return issue


class IssuePublisherTests(unittest.TestCase):
    def setUp(self):
        self.request = WorkRequest.parse({"schema_version": 1, "request_id": "docops-issue-test",
                                          "repository_id": "docs-fixture-v1",
                                          "actions": ["check_links", "check_translation_drift"]})
        self.state = {**self.request.as_dict(), "digest": self.request.digest, "status": "completed"}
        self.report = execute(self.request)
        self.raw = (json.dumps(self.report, indent=2) + "\n").encode()
        self.api = FakeGitHub()
        self.sha = "a" * 40
        self.run = WEB + "/actions/runs/123"

    def publish(self, **kwargs):
        return publish(self.api, self.request, kwargs.get("state", self.state),
                       kwargs.get("raw", self.raw), self.sha, self.run)

    def test_issue_has_findings_pinned_source_links_and_actual_request(self):
        result = self.publish()
        body = self.api.items[0]["body"]
        self.assertEqual(result["status"], "created")
        self.assertIn(f"/blob/{self.sha}/docops/fixture/docs/en/index.md#L6", body)
        self.assertIn("docs/ko/setup.md", body)
        self.assertIn(self.request.request_id, body)
        self.assertIn("does not assess translation quality", body)
        self.assertEqual(self.api.posts, 1)

    def test_retry_reuses_closed_issue_without_rewriting_maintainer_edits(self):
        self.publish()
        self.api.items[0]["state"] = "closed"
        self.api.items[0]["body"] += "\nMaintainer notes\n"
        result = self.publish()
        self.assertEqual(result["status"], "reused")
        self.assertEqual(self.api.posts, 1)
        self.assertIn("Maintainer notes", self.api.items[0]["body"])

    def test_crash_after_post_recovers_by_listing_before_another_post(self):
        self.api.lose_response = True
        with self.assertRaises(PublicationError): self.publish()
        self.api.lose_response = False
        self.assertEqual(self.publish()["status"], "reused")
        self.assertEqual(self.api.posts, 1)

    def test_permission_error_does_not_create_issue(self):
        self.api.forbidden = True
        with self.assertRaises(PublicationError): self.publish()
        self.assertEqual(self.api.posts, 0)

    def test_uncommitted_report_is_rejected(self):
        with self.assertRaises(PublicationError): self.publish(state={**self.state, "status": "accepted"})
        self.assertEqual(self.api.posts, 0)

    def test_wrong_state_source_actions_digest_or_request_rejected(self):
        for key, value in [("repository_id", "other-repo"), ("request_id", "docops-other"),
                           ("actions", ["check_links"]), ("digest", "0" * 64)]:
            with self.subTest(key=key), self.assertRaises(PublicationError):
                self.publish(state={**self.state, key: value})
        self.assertEqual(self.api.posts, 0)

    def test_tampered_report_and_injected_mentions_or_paths_rejected(self):
        for key, value in [("request_id", "docops-other"), ("repository_id", "other-repo"),
                           ("finding_count", 99), ("schema_version", True),
                           ("actions", ["check_links"]), ("extra", "@someone")]:
            with self.subTest(key=key), self.assertRaises(PublicationError):
                self.publish(raw=json.dumps({**self.report, key: value}).encode())
        report = copy.deepcopy(self.report)
        report["findings"]["check_links"][0]["target"] = "../../secrets @someone"
        with self.assertRaises(PublicationError): self.publish(raw=json.dumps(report).encode())
        self.assertEqual(self.api.posts, 0)

    def test_conflicting_or_forged_issue_marker_fails_closed(self):
        self.publish()
        self.api.items[0]["user"]["login"] = "another-user"
        with self.assertRaises(PublicationError): self.publish()
        self.assertEqual(self.api.posts, 1)

    def test_multiple_matching_issues_fail_closed(self):
        self.publish()
        self.api.items.append(copy.deepcopy(self.api.items[0]))
        with self.assertRaises(PublicationError): self.publish()
        self.assertEqual(self.api.posts, 1)

    def test_untrusted_source_commit_or_run_url_rejected(self):
        for sha, run in [("main", self.run), (self.sha, "https://example.com/run")]:
            with self.assertRaises(PublicationError):
                issue_content(self.request, self.state, self.raw, sha, run)

    def test_duplicate_json_keys_and_oversized_evidence_rejected(self):
        with self.assertRaises(PublicationError): read_json(b'{"a":1,"a":2}')
        with self.assertRaises(PublicationError): read_json(b" " * 131073)

    def test_subset_request_cannot_publish_unrequested_translation_finding(self):
        request = WorkRequest.parse({**self.request.as_dict(), "actions": ["check_links"]})
        state = {**request.as_dict(), "digest": request.digest, "status": "completed"}
        with self.assertRaises(PublicationError): validate_report(request, state, self.report)


if __name__ == "__main__":
    unittest.main()
