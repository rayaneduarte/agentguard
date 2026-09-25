import os
import re
import sys
import boto3

from dotenv import load_dotenv
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from bedrock_agentcore.evaluation import (
    AgentInvokerInput,
    AgentInvokerOutput,
    CloudWatchAgentSpanCollector,
    DatasetClient,
    DatasetManagementServiceProvider,
    EvaluationRunConfig,
    EvaluatorConfig,
    OnDemandEvaluationDatasetRunner,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(PROJECT_ROOT / ".env")

REGION = os.getenv("AWS_REGION", "us-east-1")

HARNESS_ARN = os.getenv("AGENTGUARD_HARNESS_ARN")
LOG_GROUP = os.getenv("AGENTGUARD_LOG_GROUP")
DATASET_ID = os.getenv("AGENTGUARD_DATASET_ID")
CUSTOM_EVALUATOR_ID = os.getenv("AGENTGUARD_CUSTOM_EVALUATOR_ID")

DATASET_NAME = "agentguard_golden"
DATASET_VERSION = "1"

required_variables = {
    "AGENTGUARD_HARNESS_ARN": HARNESS_ARN,
    "AGENTGUARD_LOG_GROUP": LOG_GROUP,
    "AGENTGUARD_DATASET_ID": DATASET_ID,
    "AGENTGUARD_CUSTOM_EVALUATOR_ID": CUSTOM_EVALUATOR_ID,
}

missing_variables = [
    name
    for name, value in required_variables.items()
    if not value
]

if missing_variables:
    raise RuntimeError(
        "Variáveis de ambiente ausentes: "
        + ", ".join(missing_variables)
        + ". Configure-as no arquivo .env da raiz do projeto."
    )

EVALUATORS = [
    "Builtin.GoalSuccessRate",
    "Builtin.Helpfulness",
    CUSTOM_EVALUATOR_ID,
]

agentcore_client = boto3.client(
    "bedrock-agentcore",
    region_name=REGION,
)


def agent_invoker(
    invoker_input: AgentInvokerInput,
) -> AgentInvokerOutput:
    """
    Executa um turno do Golden Dataset no AgentGuard Harness.

    O OnDemandEvaluationDatasetRunner mantém o mesmo session_id
    entre os turnos pertencentes ao mesmo cenário.
    """

    payload = invoker_input.payload

    # Segundo o SDK, payload pode ser str ou dict.
    if isinstance(payload, dict):
        prompt = (
            payload.get("prompt")
            or payload.get("input")
            or payload.get("text")
            or str(payload)
        )
    else:
        prompt = str(payload)

    print("\n" + "-" * 60)
    print(f"Session: {invoker_input.session_id}")
    print(f"USER: {prompt}")

    response = agentcore_client.invoke_harness(
        harnessArn=HARNESS_ARN,
        runtimeSessionId=invoker_input.session_id,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "text": prompt,
                    }
                ],
            }
        ],
    )

    output_text = ""

    for event in response["stream"]:
        if "contentBlockDelta" in event:
            delta = event["contentBlockDelta"].get("delta", {})

            if "text" in delta:
                output_text += delta["text"]

        elif "runtimeClientError" in event:
            message = event["runtimeClientError"].get(
                "message",
                "Erro desconhecido durante a execução do Harness.",
            )
            raise RuntimeError(message)

        elif "validationException" in event:
            raise RuntimeError(
                f"Erro de validação do Harness: "
                f"{event['validationException']}"
            )

        elif "internalServerException" in event:
            raise RuntimeError(
                f"Erro interno do Harness: "
                f"{event['internalServerException']}"
            )

        # Remove blocos de raciocínio interno antes da avaliação.
        # Os avaliadores devem receber somente a resposta final do AgentGuard.
        clean_output = re.sub(
            r"<thinking>.*?</thinking>",
            "",
            output_text,
            flags=re.DOTALL | re.IGNORECASE,
        ).strip()

        print(f"AGENTGUARD (RAW): {output_text}")
        print(f"AGENTGUARD (FINAL): {clean_output}")

        return AgentInvokerOutput(
            agent_output=clean_output,
        )


def main():
    print("=" * 60)
    print("AgentGuard - AgentCore Evaluations")
    print("Final - Prompt Hardened")
    print("=" * 60)

    # ---------------------------------------------------------
    # 1. Golden Dataset publicado no AgentCore
    # ---------------------------------------------------------

    dataset_client = DatasetClient(
        region_name=REGION,
    )

    dataset_provider = DatasetManagementServiceProvider(
        dataset_id=DATASET_ID,
        version_id=DATASET_VERSION,
        client=dataset_client,
    )

    dataset = dataset_provider.get_dataset()

    print(f"\nDataset: {DATASET_NAME}")
    print(f"Dataset ID: {DATASET_ID}")
    print(f"Versão: {DATASET_VERSION}")
    print(f"Cenários carregados: {len(dataset.scenarios)}")

    # ---------------------------------------------------------
    # 2. CloudWatch / traces
    # ---------------------------------------------------------

    span_collector = CloudWatchAgentSpanCollector(
        log_group_name=LOG_GROUP,
        region=REGION,
    )

    # ---------------------------------------------------------
    # 3. Avaliadores
    # ---------------------------------------------------------

    config = EvaluationRunConfig(
        evaluator_config=EvaluatorConfig(
            evaluator_ids=EVALUATORS,
        ),
        evaluation_delay_seconds=180,
        max_concurrent_scenarios=1,
    )

    print(f"Avaliadores: {', '.join(EVALUATORS)}")

    # ---------------------------------------------------------
    # 4. Runner
    # ---------------------------------------------------------

    runner = OnDemandEvaluationDatasetRunner(
        region=REGION,
    )

    print("\nIniciando avaliação final do AgentGuard...")
    print("Após as invocações, o runner aguardará a ingestão dos traces.")
    print()

    result = runner.run(
        agent_invoker=agent_invoker,
        dataset=dataset,
        span_collector=span_collector,
        config=config,
    )

    # ---------------------------------------------------------
    # 5. Resultados
    # ---------------------------------------------------------

    print("\n" + "=" * 60)
    print("AVALIAÇÃO CONCLUÍDA")
    print("=" * 60)

    print(
        f"Cenários processados: "
        f"{len(result.scenario_results)}"
    )

    for scenario in result.scenario_results:
        print("\n" + "-" * 60)

        print(f"Cenário: {scenario.scenario_id}")
        print(f"Status: {scenario.status}")
        print(f"Session: {scenario.session_id}")

        if scenario.error:
            print(f"Erro: {scenario.error}")
            continue

        for evaluator in scenario.evaluator_results:
            print(f"\n{evaluator.evaluator_id}")

            for evaluation in evaluator.results:

                if "errorCode" in evaluation:
                    print(
                        f"  ERRO: {evaluation.get('errorCode')} - "
                        f"{evaluation.get('errorMessage')}"
                    )
                    continue

                print(f"  Value: {evaluation.get('value')}")
                print(f"  Label: {evaluation.get('label')}")

                explanation = evaluation.get("explanation")

                if explanation:
                    print(f"  Explanation: {explanation}")


if __name__ == "__main__":
    main()