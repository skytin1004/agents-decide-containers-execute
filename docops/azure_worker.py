"""One queue message per finite Container Apps Job execution."""
import json
import threading

from azure.core.exceptions import HttpResponseError
from azure.storage.blob import ContentSettings

from .azure_io import AzureStore
from .checks import execute, markdown_report
from .contracts import InvalidRequest, RequestConflict, WorkRequest


def event(name, **fields):
    print(json.dumps({"event": name, **fields}), flush=True)


def run_one():
    store = AzureStore()
    message = next(iter(store.queue.receive_messages(messages_per_page=1, visibility_timeout=120)), None)
    if message is None:
        event("idle")
        return 0
    request = None
    lease = None
    stopped = threading.Event()
    lost = threading.Event()
    receipt = [message.pop_receipt]
    heartbeat = None
    try:
        request = WorkRequest.parse(json.loads(message.content))
        blob, state = store.ensure_request(request)
        if state["status"] == "completed":
            store.queue.delete_message(message.id, receipt[0])
            event("duplicate", request_id=request.request_id)
            return 0
        try:
            lease = blob.acquire_lease(lease_duration=60)
        except HttpResponseError as exc:
            if exc.error_code in {"LeaseAlreadyPresent", "LeaseIsBreakingAndCannotBeAcquired"}:
                event("busy", request_id=request.request_id)
                return 0
            raise
        # Check again under the lease: another worker may have completed first.
        state = json.loads(blob.download_blob(lease=lease).readall())
        if state["status"] == "completed":
            store.queue.delete_message(message.id, receipt[0])
            event("duplicate", request_id=request.request_id)
            return 0
        if message.dequeue_count > 3:
            raise InvalidRequest("Delivery attempt limit exceeded")

        def renew():
            while not stopped.wait(20):
                try:
                    lease.renew()
                    updated = store.queue.update_message(message.id, receipt[0], visibility_timeout=120)
                    receipt[0] = updated.pop_receipt
                except Exception:
                    lost.set()
                    return

        heartbeat = threading.Thread(target=renew, daemon=True)
        heartbeat.start()
        event("started", request_id=request.request_id, actions=list(request.actions), attempt=message.dequeue_count)
        result = execute(request)
        if lost.is_set():
            raise RuntimeError("Lease or queue visibility renewal failed")
        # Deterministic reports are safe to rewrite; completion is committed under a lease.
        for name, content, kind in [
            ("report.json", json.dumps(result, indent=2) + "\n", "application/json"),
            ("report.md", markdown_report(result), "text/markdown; charset=utf-8"),
        ]:
            store.container.upload_blob(f"reports/{request.request_id}/{name}", content, overwrite=True,
                                        content_settings=ContentSettings(content_type=kind))
        stopped.set()
        heartbeat.join()
        if lost.is_set():
            raise RuntimeError("Worker lost its lease before completion")
        state["status"] = "completed"
        blob.upload_blob(json.dumps(state), overwrite=True, lease=lease,
                         content_settings=ContentSettings(content_type="application/json"))
        store.queue.delete_message(message.id, receipt[0])
        event("completed", request_id=request.request_id, finding_count=result["finding_count"])
        return 0
    except (InvalidRequest, RequestConflict, json.JSONDecodeError) as exc:
        stopped.set()
        if heartbeat:
            heartbeat.join()
        # A failed poison-queue write leaves the original message available for retry.
        store.poison.send_message(json.dumps({"reason": str(exc), "payload": message.content}), time_to_live=604800)
        store.queue.delete_message(message.id, receipt[0])
        event("poison", request_id=request.request_id if request else None, reason=str(exc))
        return 0
    except Exception as exc:
        event("failed", request_id=request.request_id if request else None, error_type=type(exc).__name__)
        # Do not delete: Azure Storage makes the message visible after the timeout.
        return 1
    finally:
        stopped.set()
        if heartbeat:
            heartbeat.join()
        if lease:
            try:
                lease.release()
            except HttpResponseError:
                pass


if __name__ == "__main__":
    raise SystemExit(run_one())
