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


def test_sam_template_defines_api_schedule_and_scoped_permissions():
    template = yaml.load(Path("infra/template.yaml").read_text(), Loader=CloudFormationLoader)
    resources = template["Resources"]
    assert resources["DashboardApi"]["Type"] == "AWS::Serverless::HttpApi"
    assert resources["ApiFunction"]["Properties"]["Handler"] == "lambda_handlers.api_handler.lambda_handler"
    schedule = resources["OrchestratorFunction"]["Properties"]["Events"]["ScheduledCheck"]
    assert schedule["Properties"]["Schedule"] == "rate(15 minutes)"
    rendered = Path("infra/template.yaml").read_text()
    assert "dynamodb:*" not in rendered
    assert "bedrock:*" not in rendered
