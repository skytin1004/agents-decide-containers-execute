# Architecture and completion semantics

## Responsibilities

The Routine supplies the trigger and input. The hosted agent maps the caller's request to `check_links`, `check_translation_drift`, both, or no action. `submit_checks` constructs and validates a four-field request. Azure Storage Queue holds work until an event-triggered Container Apps Job retrieves it. The worker writes deterministic JSON and Markdown reports to Blob Storage.

The queue scaler observes queue length; the worker must still receive, renew visibility, and delete messages. Each container processes at most one message, then exits. The Job is configured for zero to two concurrent executions, with one replica per execution.

## Three observations, three meanings

| Observation | What it proves |
| --- | --- |
| Routine dispatch accepted | The Routine service accepted a dispatch request |
| Agent returns `queued` | The validated tool submitted a queue message |
| Request state is `completed` and report exists | The worker wrote reports and committed completion |

A completed Routine run does not prove that the asynchronous worker has completed. Use the stable `request_id` to connect the model output, worker log, and stored report.

## Request identity and repeated delivery

The canonical payload sorts actions before hashing. The first submission creates `requests/{request_id}.json` using create-if-absent semantics. A conflicting payload is rejected. Repeated submissions can enqueue multiple messages while work is pending.

The worker acquires a 60-second lease on the state blob and checks completion again while holding it. It renews that lease and the 120-second queue visibility timeout every 20 seconds. Once reports are written, it commits `completed` under the lease, then deletes the queue message. If deletion fails after the commit, the next delivery sees completion and acknowledges without repeating the checks.

The report contents are deterministic, so an interrupted worker can safely rewrite them. This property does not generalize to sending emails, charging accounts, or changing external repositories. Those side effects need their own idempotency protocol. There is no exactly-once execution guarantee.

## Failure behavior

Invalid messages and request conflicts go to `docops-poison`. A message that reaches a fourth delivery without completing also goes to poison. Contending workers can increase delivery counts; the sample does not distinguish infrastructure retries from useful attempts. A transient worker exception leaves the message invisible until its timeout expires. Azure Job replica retries are disabled so queue redelivery owns retry timing.

The local rehearsal simulates failure with `--fail-once`, uses SQLite leases with owner fencing, and marks its third failed attempt as poison. Local and cloud transports demonstrate the same principles but intentionally have different retry machinery.

The sample does not automatically change request state to `failed` when a message is poisoned. Operators must inspect the poison queue; a pending status can require intervention. There is no automatic poison replay. Use a new ID after diagnosing an invalid payload.

## Identity and access

The hosted agent's `instance_identity.principal_id` receives Blob Data Contributor and Queue Data Message Sender on the demo storage account. The worker uses a dedicated user-assigned managed identity with Blob and Queue Data Contributor plus AcrPull. No storage account keys or model API keys are stored.

These built-in roles are convenient for the sample but cover more than the minimal operations. Production deployments can narrow roles and scopes further. The Foundry project identity and hosted agent instance identity are different principals. Read the returned agent identity instead of guessing it.

## Production extensions

Add an outbox or reconciler for accepted-but-not-enqueued requests; poison alerts and recovery; retention and data classification; request-level authorization; controlled repository acquisition; comprehensive Markdown parsing; dependency supply-chain checks; and load/failure testing. This repository demonstrates a bounded workflow, not a production operations platform.
