from pathlib import Path

import yaml


class CloudFormationLoader(yaml.SafeLoader):
    pass


def _tag(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_mapping(node)


CloudFormationLoader.add_multi_constructor("!", _tag)


def _load_template() -> dict:
    return yaml.load(
        Path("infra/template.yaml").read_text(), Loader=CloudFormationLoader
    )


def _policy_actions(function: dict) -> list[str]:
    """Flatten the Action entries from a function's inline Policies."""
    actions: list[str] = []
    for policy in function["Properties"]["Policies"]:
        for statement in policy["Statement"]:
            action = statement["Action"]
            actions.extend(action if isinstance(action, list) else [action])
    return actions


def test_sam_template_defines_api_schedule_and_scoped_permissions():
    resources = _load_template()["Resources"]

    # REST surface consumed by the dashboard.
    api = resources["CommandCenterApi"]
    assert api["Type"] == "AWS::Serverless::HttpApi"
    assert api["Properties"]["StageName"] == "prod"
    api_function = resources["ApiFunction"]["Properties"]
    assert api_function["Handler"] == "lambda_handlers.api_handler.lambda_handler"
    proxy = api_function["Events"]["ProxyApi"]
    assert proxy["Type"] == "HttpApi"
    assert proxy["Properties"]["ApiId"] == "CommandCenterApi"
    assert proxy["Properties"]["Path"] == "/{proxy+}"

    # Scheduled Orchestrator wired to the parameterized EventBridge rule.
    orchestrator = resources["OrchestratorFunction"]["Properties"]
    assert orchestrator["Handler"] == "lambda_handlers.orchestrator_handler.lambda_handler"
    schedule = orchestrator["Events"]["ScheduledCheck"]["Properties"]
    assert schedule["Schedule"] == "ScheduleExpression"
    assert schedule["Name"] == "cashflow-guardian-scheduled-check"


def test_sam_template_uses_scoped_iam_and_send_mode_parameter():
    template = _load_template()
    resources = template["Resources"]
    params = template["Parameters"]

    # Regression guard: SAM's Globals.Function does not support `Policies`
    # (putting it there fails `sam build` with InvalidGlobalsSectionException).
    assert "Policies" not in template["Globals"]["Function"]

    orchestrator_actions = _policy_actions(resources["OrchestratorFunction"])
    api_actions = _policy_actions(resources["ApiFunction"])

    # Least-privilege: no wildcard grants, and the deterministic REST handler is
    # not given Bedrock access (only the Orchestrator invokes the model).
    for actions in (orchestrator_actions, api_actions):
        assert "dynamodb:*" not in actions
        assert "bedrock:*" not in actions
        assert "dynamodb:Scan" in actions
        assert "logs:PutLogEvents" in actions
    assert "bedrock:InvokeModel" in orchestrator_actions
    assert "bedrock:InvokeModel" not in api_actions

    # SendMode drives CASHFLOW_SEND_MODE (log = dry-run demos, live = real Gmail).
    assert params["SendMode"]["Default"] == "log"
    assert params["SendMode"]["AllowedValues"] == ["log", "live"]

    # Both tables and the API endpoint are exported for the deploy script.
    outputs = template["Outputs"]
    assert set(outputs) == {"ClientsTableName", "PendingActionsTableName", "ApiEndpoint"}
    assert "/prod" in outputs["ApiEndpoint"]["Value"]


def test_sam_template_builds_from_the_staged_backend_only():
    """CodeUri must point at the staged backend, never the repo root.

    With `CodeUri: ..` sam build packages frontend/node_modules and the venvs
    (the repo is >1 GB), which exceeds Lambda's package limit.
    """
    template = _load_template()
    assert template["Globals"]["Function"]["CodeUri"] == "../.lambda_build"
    # Runtime must match the interpreter the package is staged from (.venv).
    assert template["Globals"]["Function"]["Runtime"] == "python3.12"
