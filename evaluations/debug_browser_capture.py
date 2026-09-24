import boto3
import json
import uuid
import re
import os

from pathlib import Path
from dotenv import load_dotenv


# ============================================================
# Configuração do projeto
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Carrega o .env localizado na raiz do projeto.
load_dotenv(PROJECT_ROOT / ".env")

REGION = "us-east-1"
MODEL_ID = "us.amazon.nova-lite-v1:0"

HARNESS_ARN = os.getenv("AGENTGUARD_HARNESS_ARN")

if not HARNESS_ARN:
    raise RuntimeError(
        "AGENTGUARD_HARNESS_ARN não foi encontrada. "
        "Defina essa variável no arquivo .env da raiz do projeto."
    )

OUTPUT_FILE = PROJECT_ROOT / "evaluations" / "browser-capture-test.json"


# ============================================================
# Prompt diagnóstico
# ============================================================

PROMPT = """
Use obrigatoriamente a ferramenta browser para acessar https://example.com.
Leia o título principal exibido na página usando o navegador.
Depois informe qual conteúdo foi encontrado.
Não responda apenas com conhecimento interno.
"""


# ============================================================
# Invocação do Harness
# ============================================================

client = boto3.client(
    "bedrock-agentcore",
    region_name=REGION,
)

session_id = str(uuid.uuid4())

response = client.invoke_harness(
    harnessArn=HARNESS_ARN,
    runtimeSessionId=session_id,
    messages=[
        {
            "role": "user",
            "content": [{"text": PROMPT}],
        }
    ],
)

# ============================================================
# Captura do stream e do conteúdo recuperado pelo Browser
# ============================================================

raw_events = []
all_text = ""
retrieval_context = []

print("\n=== STREAM DO HARNESS ===\n")

for event in response["stream"]:
    raw_events.append(event)

    # Continua mostrando todos os eventos ao vivo no terminal.
    print(json.dumps(event, ensure_ascii=False, default=str))

    if "contentBlockDelta" not in event:
        continue

    delta = event["contentBlockDelta"].get("delta", {})

    # Texto produzido pelo modelo.
    if "text" in delta:
        all_text += delta["text"]

    # Resultado real retornado pela ferramenta.
    if "toolResult" in delta:
        for item in delta["toolResult"]:
            if "text" not in item:
                continue

            text = item["text"]

            # Captura somente conteúdo efetivamente recuperado
            # da página pelo Browser.
            if text.startswith("Text content:"):
                retrieval_context.append(text)


# ============================================================
# Tratamento da resposta
# ============================================================

# Remove blocos <thinking>...</thinking> do texto acumulado.
actual_output = re.sub(
    r"<thinking>.*?</thinking>",
    "",
    all_text,
    flags=re.DOTALL,
).strip()


# ============================================================
# Persistência do resultado diagnóstico
# ============================================================

result = {
    "session_id": session_id,
    "model_id": MODEL_ID,
    "prompt": PROMPT.strip(),
    "retrieval_context": retrieval_context,
    "actual_output": actual_output,
    "raw_events": raw_events,
}

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

with OUTPUT_FILE.open("w", encoding="utf-8") as f:
    json.dump(
        result,
        f,
        ensure_ascii=False,
        indent=2,
        default=str,
    )


# ============================================================
# Resumo no terminal
# ============================================================

print("\n\n=== RETRIEVAL CONTEXT ===\n")

for context in retrieval_context:
    print(context)

print("\n=== RESPOSTA FINAL ===\n")
print(actual_output)

print("\n=== ARQUIVO SALVO ===")
print(OUTPUT_FILE)