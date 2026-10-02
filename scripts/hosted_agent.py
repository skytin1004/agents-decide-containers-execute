"""Deploy a dedicated agent from a whitelist archive; inspect or invoke it."""
import argparse
import io
import json
import os
import zipfile
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    AgentEndpointConfig, CodeConfiguration, CodeDependencyResolution,
    FixedRatioVersionSelectionRule, HostedAgentDefinition, ProtocolConfiguration,
    ProtocolVersionRecord, ResponsesProtocolConfiguration, VersionSelector,
)
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def code_archive():
    buffer = io.BytesIO()
    buffer.name = "docops-agent.zip"
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(ROOT / "agent/main.py", "main.py")
        archive.write(ROOT / "requirements-cloud.txt", "requirements.txt")
        for path in sorted((ROOT / "docops").rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix in {".py", ".md", ".json"}:
                archive.write(path, path.relative_to(ROOT).as_posix())
    buffer.seek(0)
    return buffer


def main():
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["deploy", "show", "route", "invoke"])
    parser.add_argument("--version")
    parser.add_argument("--message", default="request_id: docops-demo-001. Check broken links and translation drift in docs-fixture-v1.")
    args = parser.parse_args()
    name = os.getenv("FOUNDRY_HOSTED_AGENT_NAME", "docops-agent")
    endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
    with DefaultAzureCredential() as credential, AIProjectClient(endpoint=endpoint, credential=credential) as project:
        if args.command == "deploy":
            result = project.agents.create_version_from_code(
                agent_name=name, description="Documentation checks for the October 14 session",
                definition=HostedAgentDefinition(cpu="0.5", memory="1Gi",
                    code_configuration=CodeConfiguration(runtime="python_3_13",
                        entry_point=["python", "main.py"],
                        dependency_resolution=CodeDependencyResolution.REMOTE_BUILD),
                    environment_variables={
                        "FOUNDRY_PROJECT_ENDPOINT": endpoint,
                        "FOUNDRY_MODEL_NAME": os.environ["FOUNDRY_MODEL_NAME"],
                        "AZURE_STORAGE_ACCOUNT": os.environ["AZURE_STORAGE_ACCOUNT"],
                    },
                    protocol_versions=[ProtocolVersionRecord(protocol="responses", version="2.0.0")]),
                code=code_archive())
        elif args.command == "show":
            result = (project.agents.get_version(agent_name=name, agent_version=args.version)
                      if args.version else project.agents.get(agent_name=name))
        elif args.command == "route":
            if not args.version:
                parser.error("--version is required for route")
            version = project.agents.get_version(agent_name=name, agent_version=args.version)
            if version["status"] != "active":
                raise RuntimeError("Route only an active version")
            result = project.agents.update_details(agent_name=name, agent_endpoint=AgentEndpointConfig(
                version_selector=VersionSelector(version_selection_rules=[
                    FixedRatioVersionSelectionRule(agent_version=args.version, traffic_percentage=100)]),
                protocol_configuration=ProtocolConfiguration(responses=ResponsesProtocolConfiguration())))
        else:
            with project.get_openai_client(agent_name=name) as client:
                result = client.responses.create(input=args.message)
        data = result.as_dict() if hasattr(result, "as_dict") else result.model_dump(mode="json")
        print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
