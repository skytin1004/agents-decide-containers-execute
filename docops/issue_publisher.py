"""Publish validated fixed-fixture results to one configured GitHub repository.

The workflow serializes publishers. An Issue marker supports recovery after a
successful POST with a lost response; GitHub does not provide exactly-once POST.
"""
import hashlib
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .checks import execute
from .contracts import WorkRequest

DESTINATION = "skytin1004/agents-decide-containers-execute"
WEB = f"https://github.com/{DESTINATION}"
API = f"https://api.github.com/repos/{DESTINATION}"
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
MAX_JSON_BYTES = 131072


class PublicationError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def read_json(data):
    if len(data) > MAX_JSON_BYTES:
        raise PublicationError("Evidence exceeds the size limit")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise PublicationError("Duplicate JSON key")
            result[key] = value
        return result

    def reject_constant(value):
        raise PublicationError("Non-finite JSON number")

    return json.loads(data, object_pairs_hook=unique, parse_constant=reject_constant)


def validate_state(request, state):
    expected = {**request.as_dict(), "digest": request.digest, "status": state.get("status")}
    if canonical(state) != canonical(expected):
        raise PublicationError("Stored request does not match the requested source, actions and digest")
    if state["status"] not in {"accepted", "completed"}:
        raise PublicationError("Unexpected request status")


def validate_report(request, state, report):
    validate_state(request, state)
    if state["status"] != "completed":
        raise PublicationError("Report is not committed")
    # This deliberately small demo uses an immutable fixture. Recompute its
    # deterministic result to reject altered paths, prose, counts or actions.
    # This is a consistency check, not proof of the cloud image provenance.
    if canonical(report) != canonical(execute(request)):
        raise PublicationError("Report does not match the approved fixture and request")


def marker(request):
    return f"<!-- docops-request: {request.request_id} -->"


def issue_content(request, state, report_bytes, source_commit, run_url):
    report = read_json(report_bytes)
    validate_report(request, state, report)
    if not COMMIT.fullmatch(source_commit):
        raise PublicationError("Source links require a full commit SHA")
    if not re.fullmatch(re.escape(WEB) + r"/actions/runs/[1-9][0-9]*", run_url):
        raise PublicationError("Workflow URL must belong to the fixed destination")
    digest = hashlib.sha256(report_bytes).hexdigest()
    source = f"{WEB}/blob/{source_commit}/docops/fixture"
    count = report["finding_count"]
    title = f"Documentation check: {count} item{'s' if count != 1 else ''} need{'s' if count == 1 else ''} attention"
    lines = ["## Documentation review needed", "",
             "The Azure worker completed the requested checks. The following items need a maintainer’s review.", ""]
    for finding in report["findings"].get("check_links", []):
        path, line, target = finding["file"], finding["line"], finding["target"]
        lines += ["### Broken internal link", "",
                  f"[{path}, line {line}]({source}/{path}#L{line}) points to `{target}`, which is missing from the approved snapshot.", "",
                  "- [ ] Fix the link or add the intended document.", ""]
    for finding in report["findings"].get("check_translation_drift", []):
        path, original = finding["file"], finding["source"]
        lines += ["### Translation baseline needs review", "",
                  f"[{path}]({source}/{path}) needs review against [{original}]({source}/{original}). The source hash differs from the recorded translation baseline.", "",
                  "This flags a changed source; it does not assess translation quality or generate a translation.", "",
                  "- [ ] Review the translated page and update its baseline after review.", ""]
    lines += ["<details>", "<summary>Execution evidence</summary>", "",
              f"- Request: `{request.request_id}`",
              f"- Approved source: `{request.repository_id}`",
              f"- Checks: {', '.join(f'`{a}`' for a in request.actions)}",
              "- Application state: **completed** before Issue publication",
              f"- Report: `reports/{request.request_id}/report.json` in Azure Blob Storage",
              f"- Report SHA-256: `{digest}`",
              f"- [Workflow run and downloadable evidence]({run_url})",
              f"- Source links use commit `{source_commit}`", "",
              "The agent selected the checks. The Container Apps Job ran them and committed the report. A bounded GitHub Actions publisher validated that report and opened this Issue. No source files were edited and no pull request was created.", "",
              "The request state and report identify application completion. They do not contain a Job execution ID or a model reasoning trace. The publisher verifies agreement with the fixed fixture; it does not independently attest the worker image.", "",
              "</details>", "", marker(request),
              f"<!-- docops-request-digest: {request.digest} -->",
              f"<!-- docops-report-sha256: {digest} -->", ""]
    return {"title": title, "body": "\n".join(lines)}, report, digest


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise PublicationError("GitHub API redirects are not accepted")


class GitHub:
    def __init__(self, token):
        if not token:
            raise PublicationError("GITHUB_TOKEN is required")
        self.token = token

    def call(self, method, path, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        request = Request(API + path, data=data, method=method, headers={
            "Authorization": "Bearer " + self.token, "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json",
            "User-Agent": "bounded-docops-issue-publisher"})
        try:
            with build_opener(NoRedirect()).open(request, timeout=30) as response:
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise PublicationError("GitHub response too large")
                return json.loads(raw)
        except HTTPError as exc:
            raise PublicationError(f"GitHub {method} returned HTTP {exc.code}; no blind POST retry") from None
        except (URLError, TimeoutError) as exc:
            raise PublicationError("GitHub request failed; rerun to discover an existing Issue before posting") from None

    def issues(self):
        # List directly, including closed Issues; do not depend on search indexing.
        for page in range(1, 101):
            batch = self.call("GET", f"/issues?state=all&per_page=100&page={page}")
            if not isinstance(batch, list):
                raise PublicationError("Invalid Issue listing")
            yield from (item for item in batch if "pull_request" not in item)
            if len(batch) < 100:
                return
        raise PublicationError("Issue listing limit reached; refusing an incomplete duplicate check")

    def create(self, content):
        return self.call("POST", "/issues", content)


def publish(api, request, state, report_bytes, source_commit, run_url):
    content, report, digest = issue_content(request, state, report_bytes, source_commit, run_url)
    receipt = {"request_id": request.request_id, "request_digest": request.digest,
               "report_sha256": digest, "source_commit": source_commit, "workflow_url": run_url}
    if not report["finding_count"]:
        return {**receipt, "status": "no_findings", "issue_url": None}
    matches = [item for item in api.issues() if marker(request) in (item.get("body") or "")]
    if len(matches) > 1:
        raise PublicationError("Multiple Issues match this request; human reconciliation required")
    if matches:
        issue = matches[0]
        body = issue.get("body") or ""
        if (issue.get("user", {}).get("login") != "github-actions[bot]" or
                f"<!-- docops-request-digest: {request.digest} -->" not in body or
                f"<!-- docops-report-sha256: {digest} -->" not in body):
            raise PublicationError("Existing Issue has conflicting identity or evidence")
        status = "reused"
    else:
        issue = api.create(content)
        status = "created"
    number = issue.get("number")
    url = issue.get("html_url")
    if (type(number) is not int or number <= 0 or url != f"{WEB}/issues/{number}" or
            issue.get("user", {}).get("login") != "github-actions[bot]"):
        raise PublicationError("Unexpected Issue identity returned by GitHub")
    return {**receipt, "status": status, "issue_number": number, "issue_url": url}
