import json
from pathlib import Path

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


if __name__ == "__main__":
    print(lookup_policy("standard_access"))

