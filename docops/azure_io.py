"""Managed-identity transport. Import only in cloud mode."""
import json
import os

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.storage.queue import QueueClient

from .contracts import RequestConflict, WorkRequest


class AzureStore:
    def __init__(self):
        account = os.environ["AZURE_STORAGE_ACCOUNT"]
        credential = DefaultAzureCredential()
        self.blobs = BlobServiceClient(f"https://{account}.blob.core.windows.net", credential=credential)
        self.container = self.blobs.get_container_client(os.getenv("DOCOPS_CONTAINER", "docops-results"))
        queue_url = f"https://{account}.queue.core.windows.net"
        self.queue = QueueClient(queue_url, os.getenv("DOCOPS_QUEUE", "docops-work"), credential=credential)
        self.poison = QueueClient(queue_url, os.getenv("DOCOPS_POISON_QUEUE", "docops-poison"), credential=credential)

    def state_blob(self, request_id):
        return self.container.get_blob_client(f"requests/{request_id}.json")

    def ensure_request(self, request: WorkRequest):
        blob = self.state_blob(request.request_id)
        initial = {"digest": request.digest, "status": "accepted", **request.as_dict()}
        try:
            blob.upload_blob(json.dumps(initial), overwrite=False,
                             content_settings=ContentSettings(content_type="application/json"))
        except ResourceExistsError:
            pass
        state = json.loads(blob.download_blob().readall())
        if state["digest"] != request.digest:
            raise RequestConflict("request_id is already bound to a different payload")
        return blob, state

    def submit(self, request: WorkRequest):
        if not request.actions:
            return {"request_id": request.request_id, "status": "no_action"}
        _, state = self.ensure_request(request)
        if state["status"] == "completed":
            return {"request_id": request.request_id, "status": "duplicate", "existing_status": "completed"}
        # Retried submissions may add messages. The worker owns logical deduplication.
        self.queue.send_message(request.canonical_json(), time_to_live=604800)
        return {"request_id": request.request_id, "status": "queued"}

    def status(self, request_id):
        # Reuse the contract boundary before constructing a storage path.
        WorkRequest.parse({"schema_version": 1, "request_id": request_id,
                           "repository_id": "docs-fixture-v1", "actions": []})
        try:
            state = json.loads(self.state_blob(request_id).download_blob().readall())
        except ResourceNotFoundError:
            return {"request_id": request_id, "status": "not_found"}
        result = {"request_id": request_id, "status": state["status"]}
        if state["status"] == "completed":
            result["report"] = json.loads(self.container.download_blob(f"reports/{request_id}/report.json").readall())
        return result
