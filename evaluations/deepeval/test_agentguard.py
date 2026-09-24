import sys
import uuid
import json
import pytest
import boto3
import re
import os
from pathlib import Path
from dotenv import load_dotenv


# ============================================================
# Configuração do projeto
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# Carrega as variáveis definidas no .env da raiz do projeto.
load_dotenv(PROJECT_ROOT / ".env")


from deepeval import assert_test
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from deepeval.models import AmazonBedrockModel


REGION = "us-east-1"
MODEL_ID = "us.amazon.nova-lite-v1:0"

HARNESS_ARN = os.getenv("AGENTGUARD_HARNESS_ARN")

if not HARNESS_ARN:
    raise RuntimeError(
        "AGENTGUARD_HARNESS_ARN não foi encontrada. "
        "Defina essa variável no arquivo .env da raiz do projeto."
    )


# ============================================================
# Modelo avaliador do DeepEval
# ============================================================

JUDGE_MODEL = AmazonBedrockModel(
    model="mistral.mistral-large-3-675b-instruct",
    region=REGION,
)

print(f"DeepEval Judge: {JUDGE_MODEL.get_model_name()}")


# ============================================================
# Golden Dataset
# ============================================================

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


# ============================================================
# Execução do AgentGuard + captura do Browser
# ============================================================

def executar_com_browser_context(prompt, session_id):
    client = boto3.client(
        "bedrock-agentcore",
        region_name=REGION,
    )

    response = client.invoke_harness(
        harnessArn=HARNESS_ARN,
        runtimeSessionId=session_id,
        model={
            "bedrockModelConfig": {
                "modelId": MODEL_ID,
                "apiFormat": "converse_stream",
            }
        },
        messages=[
            {
                "role": "user",
                "content": [{"text": prompt}],
            }
        ],
    )

    texto_completo = ""
    retrieval_context = []

    for event in response["stream"]:
        if "contentBlockDelta" not in event:
            continue

        delta = event["contentBlockDelta"].get("delta", {})

        if "text" in delta:
            texto_completo += delta["text"]

        if "toolResult" in delta:
            for item in delta["toolResult"]:
                if "text" not in item:
                    continue

                conteudo = item["text"]

                # Somente conteúdo realmente recuperado pelo Browser
                # é usado como retrieval_context do Faithfulness.
                if conteudo.startswith("Text content:"):
                    retrieval_context.append(conteudo)

    # Remove blocos internos de raciocínio do modelo.
    actual_output = re.sub(
        r"<thinking>.*?</thinking>",
        "",
        texto_completo,
        flags=re.DOTALL,
    ).strip()

    return actual_output, retrieval_context


# ============================================================
# Testes DeepEval
# ============================================================

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

    # Cada cenário recebe uma sessão própria.
    # Os turnos do mesmo cenário compartilham a mesma sessão.
    session_id = f"deepeval-{uuid.uuid4()}"

    conversa = []
    retrieval_context = []

    for numero_turno, turno in enumerate(turns, start=1):
        entrada_turno = turno["input"]

        print(f"\nTurno {numero_turno}/{len(turns)}")

        resposta_turno, contexto_turno = executar_com_browser_context(
            entrada_turno,
            session_id,
        )

        retrieval_context.extend(contexto_turno)

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
        retrieval_context=retrieval_context if retrieval_context else None,
    )


    # --------------------------------------------------------
    # Answer Relevancy
    # Threshold exigido: >= 0.7
    # --------------------------------------------------------

    answer_relevancy = AnswerRelevancyMetric(
        threshold=0.7,
        model=JUDGE_MODEL,
        include_reason=True,
    )


    # --------------------------------------------------------
    # G-Eval
    # Verifica as assertions específicas de cada cenário.
    # Threshold exigido: >= 0.8
    # --------------------------------------------------------

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
        threshold=0.8,
        model=JUDGE_MODEL,
    )


    # --------------------------------------------------------
    # Faithfulness
    # Threshold exigido: >= 0.8
    # Aplicado somente quando o Browser realmente recuperou
    # conteúdo externo.
    # --------------------------------------------------------

    faithfulness = FaithfulnessMetric(
        threshold=0.8,
        model=JUDGE_MODEL,
        include_reason=True,
    )

    metrics = [
        answer_relevancy,
        agentguard_assertions,
    ]

    if retrieval_context:
        metrics.append(faithfulness)


    # --------------------------------------------------------
    # Execução das métricas
    # --------------------------------------------------------

    assert_test(
        test_case,
        metrics=metrics,
        run_async=False,
    )