import json
import os
from pathlib import Path

from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import FunctionTool, PromptAgentDefinition
from azure.identity import DefaultAzureCredential
from openai.types.responses.response_input_param import FunctionCallOutput


def _find_repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".env").exists():
            return parent
    return Path(__file__).resolve().parents[2]


REPO_ROOT = _find_repo_root()

env_path = REPO_ROOT / ".env"
load_dotenv(env_path)

PROJECT_CONNECTION_STRING = os.getenv("PROJECT_CONNECTION_STRING")
MODEL_DEPLOYMENT_NAME = os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-5.4")

POLICY_DATA_PATH = Path(__file__).resolve().parent / "policy_data.json"


def load_policies() -> list[dict]:
    with open(POLICY_DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("policies", [])


def lookup_policy(request_type: str) -> str:
    """
    Deterministically maps a request type to an approved policy.

    Supported request types:
    - standard_access
    - privileged_access
    - unsupported
    """

    mapping = {
        "standard_access": "POL-ACCESS-001",
        "privileged_access": "POL-PRIV-002",
        "unsupported": "POL-EXC-003",
    }

    policy_id = mapping.get(request_type, "POL-EXC-003")

    for policy in load_policies():
        if policy["policy_id"] == policy_id:
            return json.dumps(policy, indent=2)

    return json.dumps(
        {
            "error": "Policy not found",
            "requested_type": request_type,
        },
        indent=2,
    )


LOOKUP_POLICY_TOOL = FunctionTool(
    name="lookup_policy",
    description=(
        "Retrieve the approved IT policy for a classified request type. "
        "Use this tool instead of relying on model memory."
    ),
    parameters={
        "type": "object",
        "properties": {
            "request_type": {
                "type": "string",
                "enum": [
                    "standard_access",
                    "privileged_access",
                    "unsupported",
                ],
                "description": "The classified IT request type.",
            }
        },
        "required": ["request_type"],
        "additionalProperties": False,
    },
    strict=False,
)


class IntakeAgent:
    def __init__(self):
        self.agent = None
        self.client = None
        self.openai = None

    def create(self):
        if not PROJECT_CONNECTION_STRING:
            raise RuntimeError(
                "PROJECT_CONNECTION_STRING is not set. "
                "Complete Challenge 0 before creating the Foundry agent."
            )

        self.client = AIProjectClient(
            endpoint=PROJECT_CONNECTION_STRING,
            credential=DefaultAzureCredential(),
        )

        self.openai = self.client.get_openai_client()

        system_prompt = """
        You are the Intake Agent for an internal IT onboarding and service desk workflow.

        Your responsibilities are:
        1. Identify the user's request category.
        2. Determine whether required information is present.
        3. Collect only the minimum information required to process the request.
        4. Produce a structured request record for the next agent.

        Rules:
        - Do not grant, modify, or revoke access.
        - Do not perform password or privilege changes.
        - Do not invent missing employee details.
        - If the request is ambiguous, mark it as unclear.
        - Preserve the user's original intent without adding assumptions.
        - Do not make the final authorization decision.

        Use one of these request categories when possible:
        - standard_access
        - privileged_access
        - unsupported

        Return a concise structured response.
        """

        self.agent = self.client.agents.create_version(
            agent_name="it-service-desk-intake-agent",
            definition=PromptAgentDefinition(
                model=MODEL_DEPLOYMENT_NAME,
                instructions=system_prompt,
            ),
        )

        return self.agent

    def run(self, input_text: str) -> str:
        conversation = self.openai.conversations.create()

        response = self.openai.responses.create(
            input=input_text,
            conversation=conversation.id,
            extra_body={
                "agent_reference": {
                    "name": self.agent.name,
                    "type": "agent_reference",
                }
            },
        )

        self.openai.conversations.delete(
            conversation_id=conversation.id
        )

        return response.output_text

    def cleanup(self):
        if self.agent:
            self.client.agents.delete_version(
                agent_name=self.agent.name,
                agent_version=self.agent.version,
            )

        if self.client:
            self.client.close()


class KnowledgePolicyAgent:
    def __init__(self):
        self.agent = None
        self.client = None
        self.openai = None

    def create(self):
        if not PROJECT_CONNECTION_STRING:
            raise RuntimeError(
                "PROJECT_CONNECTION_STRING is not set. "
                "Complete Challenge 0 before creating the Foundry agent."
            )

        self.client = AIProjectClient(
            endpoint=PROJECT_CONNECTION_STRING,
            credential=DefaultAzureCredential(),
        )

        self.openai = self.client.get_openai_client()

        system_prompt = """
        You are the Knowledge & Policy Agent for an internal IT service desk workflow.

        Your responsibilities are:
        1. Review the structured request from the Intake Agent.
        2. Use the lookup_policy tool to retrieve the approved policy.
        3. Return the policy reference, policy status, risk level, allowed action,
           and whether human approval is required.

        Rules:
        - Use approved policy data only.
        - Never invent policy.
        - Never override policy restrictions.
        - Do not execute access changes.
        - If no approved policy applies, treat the request as unsupported.
        - If the request is unclear or conflicts with policy, require escalation.
        - Always include the policy ID used.

        Return a concise structured response for the next agent.
        """

        self.agent = self.client.agents.create_version(
            agent_name="it-service-desk-policy-agent",
            definition=PromptAgentDefinition(
                model=MODEL_DEPLOYMENT_NAME,
                instructions=system_prompt,
                tools=[LOOKUP_POLICY_TOOL],
            ),
        )

        return self.agent

    def run(self, input_text: str) -> str:
        conversation = self.openai.conversations.create()

        response = self.openai.responses.create(
            input=input_text,
            conversation=conversation.id,
            extra_body={
                "agent_reference": {
                    "name": self.agent.name,
                    "type": "agent_reference",
                }
            },
        )

        while True:
            function_calls = [
                item
                for item in response.output
                if item.type == "function_call"
            ]

            if not function_calls:
                break

            tool_outputs = []

            for item in function_calls:
                if item.name == "lookup_policy":
                    args = json.loads(item.arguments)
                    result = lookup_policy(args["request_type"])
                else:
                    result = json.dumps(
                        {"error": f"Unknown tool '{item.name}'"}
                    )

                tool_outputs.append(
                    FunctionCallOutput(
                        type="function_call_output",
                        call_id=item.call_id,
                        output=result,
                    )
                )

            response = self.openai.responses.create(
                input=tool_outputs,
                conversation=conversation.id,
                extra_body={
                    "agent_reference": {
                        "name": self.agent.name,
                        "type": "agent_reference",
                    }
                },
            )

        self.openai.conversations.delete(
            conversation_id=conversation.id
        )

        return response.output_text

    def cleanup(self):
        if self.agent:
            self.client.agents.delete_version(
                agent_name=self.agent.name,
                agent_version=self.agent.version,
            )

        if self.client:
            self.client.close()


class ResolutionEscalationAgent:
    def __init__(self):
        self.agent = None
        self.client = None
        self.openai = None

    def create(self):
        if not PROJECT_CONNECTION_STRING:
            raise RuntimeError(
                "PROJECT_CONNECTION_STRING is not set. "
                "Complete Challenge 0 before creating the Foundry agent."
            )

        self.client = AIProjectClient(
            endpoint=PROJECT_CONNECTION_STRING,
            credential=DefaultAzureCredential(),
        )

        self.openai = self.client.get_openai_client()

        system_prompt = """
        You are the Resolution & Escalation Agent for an internal IT service desk workflow.

        You receive:
        - the structured employee request
        - the approved policy result
        - the policy risk level
        - the human-approval requirement

        Your responsibilities are:
        1. Determine whether the request is low-risk and pre-authorized.
        2. Prepare only an approved low-risk action.
        3. Route sensitive, uncertain, unsupported, or exception requests
           to human approval.
        4. Return the final decision and reason.

        Rules:
        - Never perform autonomous privilege escalation.
        - Administrative or elevated access always requires human approval.
        - Policy exceptions always require human approval.
        - Missing or conflicting policy requires escalation.
        - If confidence is insufficient, escalate instead of guessing.
        - Recommendation and execution must remain separate.
        - Do not perform real access changes in this challenge.
        - Record the reason for the final decision.

        Valid final outcomes:
        - approved_for_execution
        - human_approval_required
        - needs_clarification
        - rejected_by_policy

        Return a concise structured response.
        """

        self.agent = self.client.agents.create_version(
            agent_name="it-service-desk-resolution-agent",
            definition=PromptAgentDefinition(
                model=MODEL_DEPLOYMENT_NAME,
                instructions=system_prompt,
            ),
        )

        return self.agent

    def run(self, input_text: str) -> str:
        conversation = self.openai.conversations.create()

        response = self.openai.responses.create(
            input=input_text,
            conversation=conversation.id,
            extra_body={
                "agent_reference": {
                    "name": self.agent.name,
                    "type": "agent_reference",
                }
            },
        )

        self.openai.conversations.delete(
            conversation_id=conversation.id
        )

        return response.output_text

    def cleanup(self):
        if self.agent:
            self.client.agents.delete_version(
                agent_name=self.agent.name,
                agent_version=self.agent.version,
            )

        if self.client:
            self.client.close()


if __name__ == "__main__":
    print("Local validation only.")

    for request_type in [
        "standard_access",
        "privileged_access",
        "unsupported",
    ]:
        print(f"\n=== {request_type} ===")
        print(lookup_policy(request_type))

