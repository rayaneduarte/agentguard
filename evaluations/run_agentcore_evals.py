import boto3

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


REGION = "us-east-1"

HARNESS_ARN = (
    "arn:aws:bedrock-agentcore:us-east-1:814650855304:"
    "harness/agentguard_AgentGuardHarness-ILJDUaomOZ"
)

LOG_GROUP = (
    "/aws/bedrock-agentcore/runtimes/"
    "harness_agentguard_AgentGuardHarness-GZo8bpGnin-DEFAULT"
)

DATASET_NAME = "agentguard_golden"
DATASET_ID = "agentguard_agentguard_golden-t3EGtqBLkb"
DATASET_VERSION = "1"

EVALUATORS = [
    "Builtin.GoalSuccessRate",
    "Builtin.Helpfulness",
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

    print(f"AGENTGUARD: {output_text}")

    return AgentInvokerOutput(
        agent_output=output_text,
    )


def main():
    print("=" * 60)
    print("AgentGuard - AgentCore Evaluations")
    print("Baseline v1")
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
        max_concurrent_scenarios=3,
    )

    print(f"Avaliadores: {', '.join(EVALUATORS)}")

    # ---------------------------------------------------------
    # 4. Runner
    # ---------------------------------------------------------

    runner = OnDemandEvaluationDatasetRunner(
        region=REGION,
    )

    print("\nIniciando avaliação da Baseline v1...")
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