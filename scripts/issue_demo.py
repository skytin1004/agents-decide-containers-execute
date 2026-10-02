"""Manually dispatched GitHub workflow: Routine -> committed report -> Issue."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

from azure.ai.projects import AIProjectClient
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import AzureCliCredential
from azure.storage.blob import BlobServiceClient

from docops.contracts import WorkRequest
from docops.issue_publisher import (DESTINATION, WEB, MAX_JSON_BYTES, GitHub,
                                    PublicationError, publish, read_json,
                                    validate_report, validate_state)

CHECKS = {"both": ["check_links", "check_translation_drift"],
          "links": ["check_links"], "translation": ["check_translation_drift"]}
OUTPUT = Path(".artifacts/issue-demo")


def request_from_environment():
    if os.environ.get("GITHUB_REPOSITORY") != DESTINATION or os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise PublicationError("This publisher only runs for the configured repository main branch")
    run_id = os.environ["GITHUB_RUN_ID"]
    if not run_id.isascii() or not run_id.isdigit() or int(run_id) <= 0:
        raise PublicationError("Invalid workflow run ID")
    rid = os.environ.get("INPUT_REQUEST_ID", "").strip() or f"docops-gh-{run_id}"
    return WorkRequest.parse({"schema_version": 1, "request_id": rid,
                              "repository_id": "docs-fixture-v1",
                              "actions": CHECKS[os.environ.get("INPUT_CHECKS", "both")]})


def download(container, path):
    blob = container.get_blob_client(path)
    if blob.get_blob_properties().size > MAX_JSON_BYTES:
        raise PublicationError("Blob evidence exceeds the size limit")
    raw = blob.download_blob().readall()
    read_json(raw)
    return raw


def collect(request):
    mode = os.environ.get("INPUT_MODE", "run")
    if mode not in {"run", "publish-existing"}:
        raise PublicationError("Unsupported mode")
    account = os.environ["AZURE_STORAGE_ACCOUNT"]
    # Azure/login established this CLI session with GitHub OIDC. No Azure secret.
    with AzureCliCredential() as credential, BlobServiceClient(
            f"https://{account}.blob.core.windows.net", credential=credential) as service:
        container = service.get_container_client("docops-results")
        state_path = f"requests/{request.request_id}.json"
        state = None
        try:
            state = read_json(download(container, state_path))
        except ResourceNotFoundError:
            pass
        if state is not None:
            validate_state(request, state)
        if mode == "publish-existing" and (state is None or state["status"] != "completed"):
            raise PublicationError("publish-existing requires an already completed matching request")
        if mode == "run" and (state is None or state["status"] != "completed"):
            descriptions = {
                "check_links": "check_links for broken internal documentation links",
                "check_translation_drift": "check_translation_drift for translated pages whose source baseline changed",
            }
            scope = "both documentation checks" if len(request.actions) == 2 else "this documentation check"
            prompt = (f"request_id: {request.request_id}. Repository: docs-fixture-v1. "
                      f"Run {scope} in one submission: "
                      + "; and ".join(descriptions[action] for action in request.actions)
                      + f". The actions list must contain exactly {json.dumps(list(request.actions))}. "
                      "Do not change files or publish to GitHub.")
            with AIProjectClient(endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"], credential=credential) as project:
                result = project.beta.routines.dispatch(
                    routine_name="docops-maintenance",
                    payload={"type": "invoke_agent_responses_api", "input": prompt})
                value = result.as_dict() if hasattr(result, "as_dict") else {}
                (OUTPUT / "invocation.json").write_text(json.dumps({
                    "request_id": request.request_id, "routine": "docops-maintenance",
                    "dispatch_accepted": True, "run_id": value.get("run_id", value.get("id")),
                    "observed_at": datetime.now(timezone.utc).isoformat()}, indent=2) + "\n", encoding="utf-8")
            print(f"Routine dispatch accepted for {request.request_id}; waiting for committed report", flush=True)
        else:
            print(f"Request {request.request_id} already exists; waiting/reading without redispatch", flush=True)
        deadline = time.monotonic() + 480
        while time.monotonic() < deadline:
            try:
                state_bytes = download(container, state_path)
                state = read_json(state_bytes)
            except ResourceNotFoundError:
                time.sleep(5)
                continue
            validate_state(request, state)
            if state["status"] == "completed":
                report_bytes = download(container, f"reports/{request.request_id}/report.json")
                validate_report(request, state, read_json(report_bytes))
                (OUTPUT / "request-state.json").write_bytes(state_bytes)
                (OUTPUT / "report.json").write_bytes(report_bytes)
                print(f"Committed Azure report validated for {request.request_id}", flush=True)
                return
            time.sleep(5)
        raise PublicationError("Timed out waiting for committed Azure evidence; no Issue was published")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["collect", "publish"])
    args = parser.parse_args()
    request = request_from_environment()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if args.command == "collect":
        collect(request)
        return
    receipt = publish(GitHub(os.environ["GITHUB_TOKEN"]), request,
                      read_json((OUTPUT / "request-state.json").read_bytes()),
                      (OUTPUT / "report.json").read_bytes(), os.environ["GITHUB_SHA"],
                      f"{WEB}/actions/runs/{os.environ['GITHUB_RUN_ID']}")
    receipt["published_at"] = datetime.now(timezone.utc).isoformat()
    (OUTPUT / "publication.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    summary = (f"## Documentation check\n\nRequest: `{request.request_id}`\n\n"
               f"Publication: **{receipt['status']}**\n\n"
               + (f"[Open the Issue]({receipt['issue_url']})\n" if receipt["issue_url"] else "No findings; no Issue needed.\n"))
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
        stream.write(summary)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
