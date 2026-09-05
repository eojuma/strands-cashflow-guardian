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
    params = template["Parameters"]

    # Least-privilege role: no wildcard dynamodb:* / bedrock:* grants anywhere in
    # the IAM statements (a comment in the file may still mention the phrase).
    statements = template["Globals"]["Function"]["Policies"][0]["Statement"]
    actions = [
        action
        for stmt in statements
        for action in (stmt["Action"] if isinstance(stmt["Action"], list) else [stmt["Action"]])
    ]
    assert "dynamodb:*" not in actions
    assert "bedrock:*" not in actions
    assert "bedrock:InvokeModel" in actions
    assert "dynamodb:Scan" in actions

    # SendMode drives CASHFLOW_SEND_MODE (log = dry-run demos, live = real Gmail).
    assert params["SendMode"]["Default"] == "log"
    assert params["SendMode"]["AllowedValues"] == ["log", "live"]

    # Both tables and the API endpoint are exported for the deploy script.
    outputs = template["Outputs"]
    assert set(outputs) == {"ClientsTableName", "PendingActionsTableName", "ApiEndpoint"}
    assert "/prod" in outputs["ApiEndpoint"]["Value"]
