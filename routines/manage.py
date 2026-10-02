"""Create a disabled routine, explicitly dispatch, and inspect runs."""
import argparse
import json
import os

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv


def main():
    load_dotenv()
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["create", "dispatch", "show", "runs", "delete"])
    p.add_argument("--name", default="docops-maintenance")
    p.add_argument("--request-id", default="docops-demo-001")
    p.add_argument("--message", default="Run both documentation checks in one submission: check_links for broken internal links, and check_translation_drift for stale translation baselines. The actions list must include both checks.")
    args = p.parse_args()
    prompt = f"request_id: {args.request_id}. Repository: docs-fixture-v1. {args.message}"
    with DefaultAzureCredential() as credential, AIProjectClient(
        endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"], credential=credential
    ) as project:
        routines = project.beta.routines
        if args.command == "create":
            result = routines.create_or_update(routine_name=args.name, enabled=False,
                triggers={"weekday": {"type": "schedule", "cron_expression": "0 7 * * 1-5", "time_zone": "UTC"}},
                action={"type": "invoke_agent_responses_api",
                        "agent_name": os.getenv("FOUNDRY_HOSTED_AGENT_NAME", "docops-agent"), "input": prompt})
        elif args.command == "dispatch":
            result = routines.dispatch(routine_name=args.name,
                payload={"type": "invoke_agent_responses_api", "input": prompt})
        elif args.command == "show":
            result = routines.get(routine_name=args.name)
        elif args.command == "runs":
            result = list(routines.list_runs(routine_name=args.name))
        else:
            result = routines.delete(routine_name=args.name)
        def encode(item):
            return item.as_dict() if hasattr(item, "as_dict") else str(item)
        print(json.dumps(result, default=encode, indent=2))


if __name__ == "__main__":
    main()
