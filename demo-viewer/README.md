# Execution evidence viewer

This presentation viewer keeps one request, the architecture, and its result on the same screen. It shows retained evidence without timed stage playback. Click a stage to explain it at your own pace.

## Start

From the repository root in PowerShell:

```powershell
./demo-viewer/start.ps1
```

The launcher selects the repository `.venv` when present and prints the interpreter. The built `dist` folder is included. Recorded and local modes work without the Azure SDK; local imports resolve from this repository. On macOS/Linux, run `python demo-viewer/server.py` with the intended environment active. Open `http://127.0.0.1:8765`.

Use a 1280×720 or larger viewport for presenting. The architecture and inspector fit together; the evidence sidebar scrolls independently. Narrow windows use a vertical flow.

To edit the UI, run `npm ci` and `npm run build` from `demo-viewer`. No Node server or CDN is needed to present the built viewer.

## Modes

| Mode | Button | What happens |
| --- | --- | --- |
| Recorded Azure | Load recording | Reads saved September 30, 2026 evidence for `docops-both-001`; no new execution |
| Local execution | Run locally | Runs Python validation, SQLite, worker and report export; Routine and agent choice are simulated |
| Azure Live | Dispatch to Azure | Dispatches the prepared Routine, then reads Blob request state and the matching report |
| Azure Live, existing request | Check | Reads existing request state and report without dispatching or writing to Azure |

Azure mode needs `requirements-cloud.txt`, repository `.env`, and an authenticated identity with Blob read access. See [Azure setup](../docs/azure-setup.md). The backend checks dependencies, configuration and Blob access before dispatch. Credentials remain server-side. Preflight does not guarantee downstream model or worker success.

## Explain what is proven

Badges distinguish observed, recorded, inferred, simulated and unverified information. A matching committed report establishes application completion without exposing a separate event for every upstream service. Requested checks are recovered from stored evidence; they are not a model reasoning trace.

Open report shows the findings. Raw JSON shows the loaded report. Details includes request identity, full report location, ETags and SHA-256 when available. A hash identifies the bytes; it does not independently prove where the checks ran. An absent Job execution ID is marked as not captured and is never guessed from timing.

**Open in Azure ↗** opens the observed report's Blob container in a new tab, keeping the viewer open. Follow the path beneath the button: `reports/<request-id>/report.json`. Azure opens individual Blobs in a context pane, so this link targets the container rather than promising to open the report itself. Use it for optional questions after explaining the result in the viewer. Sign in with an account that can read the container.

To enable the link, add `AZURE_STORAGE_RESOURCE_ID` to the server `.env` and restart the viewer. Get this ARM resource ID from the storage account's JSON View, or run `az storage account show --name YOUR-STORAGE-ACCOUNT --resource-group YOUR-RESOURCE-GROUP --query id -o tsv`. The account must match the observed Blob URL. No SAS or access token is included. Local execution and recordings without an account reference keep the button disabled; changing modes removes the previous destination.

View all events distinguishes viewer observations from entries labeled Recorded Azure console log. There is no live Azure console-log stream in this viewer. Logs supplement the matching request state and report; logs alone do not establish completion.

## Recovery and retention

An observation error means the reader could not verify the outcome; it does not mark the Azure Job failed. Use Check existing request with the same ID before considering a new dispatch. A missing report can mean pending work, failed work, or unavailable evidence.

Saved observations survive page reload and server restart under `.artifacts/viewer/<observation-id>/`. Local runs retain request, SQLite state, and reports. Interrupted observations become recoverable errors after restart. A restored observation is a saved snapshot; use Check for a fresh Azure read and inspect its timestamp.

Polling is sequential and stops when the observation ends. The 20-second existing-request window and 180-second new-dispatch window limit observation, not Azure execution. A viewer timeout does not cancel cloud work.

Follow the [presentation runbook](../docs/demo-runbook.md). Runtime artifacts, `.env` and credentials stay out of public packages.
