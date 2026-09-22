import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from bedrock_agentcore.evaluation import AgentInvokerInput

from deepeval import assert_test
from deepeval.metrics import AnswerRelevancyMetric
from deepeval.models import AmazonBedrockModel
from deepeval.test_case import LLMTestCase

from evaluations.run_agentcore_evals import agent_invoker


JUDGE_MODEL = AmazonBedrockModel(
    model="amazon.nova-micro-v1:0",
    region="us-east-1",
)


def test_answer_relevancy_gd01():
    entrada = (
        "Explique o que é prompt injection e dê "
        "um exemplo educativo simples."
    )

    invoker_input = AgentInvokerInput(
        payload=entrada,
        session_id=f"deepeval-{uuid.uuid4()}",
    )

    resultado = agent_invoker(invoker_input)

    resposta = resultado.agent_output

    test_case = LLMTestCase(
        input=entrada,
        actual_output=resposta,
    )

    metric = AnswerRelevancyMetric(
        threshold=0.7,
        model=JUDGE_MODEL,
        include_reason=True,
    )

    assert_test(
        test_case,
        metrics=[metric],
        run_async=False,
    )