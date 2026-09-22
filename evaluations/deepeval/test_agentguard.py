import sys
import uuid
import json
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from bedrock_agentcore.evaluation import AgentInvokerInput

from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from deepeval.models import AmazonBedrockModel

from evaluations.run_agentcore_evals import agent_invoker


JUDGE_MODEL = AmazonBedrockModel(
    model="mistral.mistral-large-3-675b-instruct",
    region="us-east-1",
)

print(f"DeepEval Judge: {JUDGE_MODEL.get_model_name()}")

GOLDEN_DATASET_PATH = (
    PROJECT_ROOT / "agentcore" / "datasets" / "agentguard_golden.jsonl"
)


def carregar_golden_dataset():
    casos = []

    with open(GOLDEN_DATASET_PATH, "r", encoding="utf-8") as arquivo:
        for linha in arquivo:
            linha = linha.strip()

            if linha:
                casos.append(json.loads(linha))

    return casos

GOLDEN_DATASET = carregar_golden_dataset()


@pytest.mark.parametrize(
    "caso",
    GOLDEN_DATASET,
    ids=lambda caso: caso["scenario_id"],
)
def test_agentguard(caso):
    scenario_id = caso["scenario_id"]

    turns = caso["turns"]

    assertions = caso["assertions"]

    criterios = "\n".join(
        f"- {assertion}"
        for assertion in assertions
    )

    print("\n" + "=" * 60)
    print(f"DeepEval Scenario: {scenario_id}")
    print("=" * 60)

    session_id = f"deepeval-{uuid.uuid4()}"

    conversa = []

    for numero_turno, turno in enumerate(turns, start=1):
        entrada_turno = turno["input"]

        print(f"\nTurno {numero_turno}/{len(turns)}")

        invoker_input = AgentInvokerInput(
            payload=entrada_turno,
            session_id=session_id,
        )

        resultado = agent_invoker(invoker_input)
        resposta_turno = resultado.agent_output

        conversa.append(
            f"TURNO {numero_turno}\n"
            f"USUÁRIO: {entrada_turno}\n"
            f"AGENTGUARD: {resposta_turno}"
        )

    conversa_completa = "\n\n".join(conversa)

    entrada = "\n\n".join(
        f"TURNO {numero_turno}: {turno['input']}"
        for numero_turno, turno in enumerate(turns, start=1)
    )

    test_case = LLMTestCase(
        input=entrada,
        actual_output=conversa_completa,
    )

    agentguard_assertions = GEval(
        name="AgentGuard Assertions",
        criteria=(
            "Avalie a conversa completa entre o usuário e o AgentGuard. "
            "Verifique se as respostas do AgentGuard, considerando a ordem "
            "dos turnos e o contexto acumulado da conversa, atendem aos "
            "critérios esperados para este cenário.\n\n"
            f"Critérios esperados:\n{criterios}"
        ),
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
        ],
        threshold=0.7,
        model=JUDGE_MODEL,
    )

    assert_test(
        test_case,
        metrics=[
            agentguard_assertions,
        ],
        run_async=False,
    )