# Sources and compatibility references

Retrieved September 30, 2026 and rechecked October 2, 2026. Recheck again before the October 14 presentation because the hosting SDK and service surface can evolve. The cloud execution evidence remains dated September 30.

- [Routines GA announcement](https://devblogs.microsoft.com/foundry/from-chatbots-to-automated-assistants-routines-in-microsoft-foundry-are-now-generally-available/) — September 24, 2026 announcement.
- [Foundry Routines concepts](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/routines) — triggers, identity, limitations, and supported agents.
- [Use Routines](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/use-routines) — create/update, manual dispatch, run history.
- [Reminder tool](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/reminder-tool) — distinct conversation-resumption feature, preview.
- [Container Apps Jobs](https://learn.microsoft.com/en-us/azure/container-apps/jobs) — finite executions, manual/scheduled/event triggers, configuration.
- [Event-driven Jobs tutorial](https://learn.microsoft.com/en-us/azure/container-apps/tutorial-event-driven-jobs) — queue scaling and worker responsibilities.
- [Container Apps Jobs samples](https://github.com/Azure-Samples/container-apps-jobs) — official executable examples.
- [Hosted-agent quickstart](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent) — hosting concepts and prerequisites.
- [Hosted-agent permissions](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agent-permissions) — deployment and runtime access.
- [Agent identity](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/agent-identity) — identity distinctions.
- [Agent tracing](https://learn.microsoft.com/en-us/azure/foundry/observability/concepts/trace-agent-concept) — observability context.
- [Official Agent Framework Responses hosted sample](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents/agent-framework/responses/01-basic) — entrypoint and ResponsesHostServer pattern adapted by this repository.

The application contract, queue/Blob integration, fixture checks, deduplication policy, and demonstration are this sample's implementation. They are not a claim of a first-party direct Routine-to-Job binding.
