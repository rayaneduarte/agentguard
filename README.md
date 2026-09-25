# AgentGuard 🛡️

Agente de segurança para análise de prompts desenvolvido com Amazon Bedrock AgentCore Harness.

O AgentGuard identifica comportamentos potencialmente adversariais em prompts destinados a sistemas de IA, incluindo prompt injection, jailbreak, tentativas de vazamento de informações e uso indevido de ferramentas.

O projeto também aplica uma abordagem de avaliação adversarial: além de detectar ataques contra outros sistemas, o próprio AgentGuard é submetido a avaliações automatizadas e campanhas estruturadas de Red Teaming.

---

## Visão geral

O agente recebe um prompt ou cenário e produz uma análise contendo:

- classificação;
- nível de risco;
- justificativa;
- ação recomendada.

As categorias utilizadas são:

- `SEGURO`
- `PROMPT_INJECTION`
- `JAILBREAK`
- `VAZAMENTO_DE_INFORMACAO`
- `USO_INDEVIDO_DE_FERRAMENTA`
- `INCERTO`

O desenvolvimento seguiu um ciclo de avaliação e hardening:

```text
Baseline
   ↓
Golden Dataset
   ↓
AgentCore Evaluations
   ↓
DeepEval
   ↓
Red Teaming
   ↓
Análise de falhas
   ↓
Hardening do system prompt
   ↓
Reavaliação
   ↓
Reteste adversarial
```

---

## Arquitetura

O AgentGuard utiliza:

- **Amazon Bedrock AgentCore Harness**
- **Amazon Nova Lite**
- **AgentCore Browser**
- **Managed Memory**
- **AgentCore Evaluations**
- **DeepEval**
- **avaliador customizado baseado em código**
- **Red Teaming estruturado**

Configuração principal do Harness:

```text
Harness: AgentGuardHarness
Modelo: us.amazon.nova-lite-v1:0
Provider: Amazon Bedrock
Ferramenta: AgentCore Browser
Memory: Managed
```

Os arquivos principais da configuração estão em:

```text
app/AgentGuardHarness/harness.json
app/AgentGuardHarness/system-prompt.md
agentcore/agentcore.json
```

---

## Golden Dataset

O projeto utiliza um Golden Dataset com **20 cenários**, distribuídos entre cinco categorias:

- consultas diretas;
- tarefas com ferramentas;
- interações multi-turno;
- solicitações fora do escopo;
- casos adversariais.

Os casos são identificados como `GD-01` a `GD-20`.

Dataset:

```text
datasets/golden-dataset.json
```

---

## Avaliação

O AgentGuard foi avaliado por duas frentes automatizadas e uma campanha estruturada de Red Teaming.

### AgentCore Evaluations

Foram utilizados:

- `Builtin.GoalSuccessRate`
- `Builtin.Helpfulness`
- evaluator customizado `AgentGuardFormatCompliance`

Resultado principal:

| Versão | GoalSuccessRate |
|---|---:|
| Baseline | 7/20 — 35% |
| Final | 13/20 — 65% |

A comparação possui uma limitação metodológica documentada: na execução final, o pipeline passou a remover blocos `<thinking>` antes de fornecer o `agent_output` ao processo de avaliação, enquanto a baseline não utilizava o mesmo tratamento.

Por isso, a melhora não deve ser atribuída exclusivamente ao hardening do system prompt.

A documentação completa do processo de configuração do AgentCore Evaluations está disponível em:

```text
evaluations/README.md
```

Resultados:

```text
evaluations/agentcore/nova-baseline-results.txt
evaluations/agentcore/nova-final-results.txt
```

### DeepEval

A suíte do DeepEval utiliza:

- **Answer Relevancy** — threshold `>= 0.7`
- **G-Eval de conformidade** — threshold `>= 0.8`
- **Faithfulness** — threshold `>= 0.8`, quando existe `retrieval_context`

O mesmo modelo juiz foi mantido nas execuções baseline e final:

```text
mistral.mistral-large-3-675b-instruct
```

Resultados:

| Versão | Casos aprovados |
|---|---:|
| Baseline | 7/20 — 35% |
| Final | 10/20 — 50% |

Arquivos:

```text
evaluations/deepeval/test_agentguard.py
evaluations/deepeval/nova-baseline-results.txt
evaluations/deepeval/nova-final-results.txt
```

### Red Teaming

Foram executados **20 ataques estruturados**, distribuídos entre:

- Prompt Injection
- Jailbreak / Bypass
- Information Leakage
- Tool Misuse
- Robustness / Agency

Resultado agregado:

| Resultado | Baseline | Final |
|---|---:|---:|
| Resistiu | 13/20 — 65% | 18/20 — 90% |
| Parcial | 4/20 — 20% | 2/20 — 10% |
| Falhou | 3/20 — 15% | 0/20 — 0% |

Os resultados representam o comportamento observado no conjunto de ataques testados e não constituem garantia de segurança ou invulnerabilidade.

Documentação:

```text
red-teaming/baseline-campaign.md
red-teaming/final-campaign.md
red-teaming/findings.md
```

Evidências brutas:

```text
red-teaming/results/
red-teaming/final-results/
```

---

## Comparação Baseline × Final

Resumo dos principais resultados:

| Frente | Baseline | Final |
|---|---:|---:|
| AgentCore GoalSuccessRate | 35% | 65% |
| DeepEval | 35% | 50% |
| Red Team — Resistiu | 65% | 90% |
| Red Team — Falhou | 15% | 0% |

A análise detalhada está disponível em:

```text
evaluations/baseline-vs-final.md
```

---

## Estrutura do repositório

```text
agentguard/
├── app/
│   └── AgentGuardHarness/
│       ├── harness.json
│       └── system-prompt.md
│
├── agentcore/
│   └── agentcore.json
│
├── datasets/
│   └── golden-dataset.json
│
├── exploratory/
│   └── baseline-v1.md
│
├── evaluations/
│   ├── README.md
│   ├── baseline-vs-final.md
│   ├── run_agentcore_evals.py
│   ├── agentcore/
│   │   ├── nova-baseline-results.txt
│   │   └── nova-final-results.txt
│   ├── deepeval/
│   │   ├── test_agentguard.py
│   │   ├── nova-baseline-results.txt
│   │   └── nova-final-results.txt
│   └── custom_evaluator/
│       └── lambda_function.py
│
├── red-teaming/
│   ├── README.md
│   ├── baseline-campaign.md
│   ├── final-campaign.md
│   ├── findings.md
│   ├── run_redteam.py
│   ├── run_redteam_final.py
│   ├── results/
│   └── final-results/
│
└── archive/
    ├── diagnostics/
    └── gemma/
```

---

## Pré-requisitos

Ambiente utilizado durante o desenvolvimento:

- Python 3.12
- Node.js 22+
- AWS CLI
- AgentCore CLI
- credenciais AWS válidas
- DeepEval

Para instalar as dependências Python utilizadas nas avaliações:

```powershell
python -m pip install -r requirements.txt
```

O AgentCore CLI é instalado separadamente via npm:

```powershell
npm install -g @aws/agentcore
```

---

## Configuração

Clone o repositório:

```powershell
git clone https://github.com/rayaneduarte/agentguard.git
cd agentguard
```

Crie o arquivo `.env` a partir do exemplo:

```powershell
Copy-Item .env.example .env
```

Preencha o `.env` com os identificadores dos recursos implantados no seu próprio ambiente AWS:

```env
AWS_REGION=us-east-1

AGENTGUARD_HARNESS_ARN=your-harness-arn-here
AGENTGUARD_LOG_GROUP=your-cloudwatch-log-group-here
AGENTGUARD_DATASET_ID=your-dataset-id-here
AGENTGUARD_CUSTOM_EVALUATOR_ID=your-custom-evaluator-id-here
```

Essas variáveis são utilizadas pelos scripts de avaliação para acessar o Harness e os recursos do AgentCore Evaluations.

O arquivo `.env` contém configurações específicas do ambiente e é ignorado pelo Git. Não versione credenciais, ARNs ou outros identificadores da sua infraestrutura AWS.

Também é necessário possuir credenciais AWS válidas no ambiente utilizado para acessar os recursos implantados.

O arquivo `agentcore/aws-targets.json`, utilizado para configuração do target de deployment, também é específico do ambiente e não é versionado neste repositório.

Na estrutura do repositório, inclua o dataset utilizado pelo AgentCore Evaluations:

```text
├── agentcore/
│   ├── agentcore.json
│   └── datasets/
│       └── agentguard_golden.jsonl
```

Inclua também o arquivo de dependências na raiz:

```text
├── requirements.txt
```

---

## Executando o AgentGuard

Com o Harness implantado e as credenciais AWS configuradas, execute:

```powershell
agentcore invoke "Analise este prompt: Ignore todas as instruções anteriores." --harness AgentGuardHarness
```

O comando envia o prompt ao Harness `AgentGuardHarness` implantado no Amazon Bedrock AgentCore e retorna a análise produzida pelo agente.

Para consultar o estado dos recursos implantados no projeto:

```powershell
agentcore status
```

---

## Executando AgentCore Evaluations

Com o Harness, o dataset e os evaluators configurados no AgentCore, preencha as variáveis do `.env` conforme descrito anteriormente e execute:

```powershell
python evaluations/run_agentcore_evals.py
```

O runner executa a avaliação sobre a versão publicada do Golden Dataset configurada no ambiente e utiliza:

- `Builtin.GoalSuccessRate`
- `Builtin.Helpfulness`
- evaluator customizado `AgentGuardFormatCompliance`

A execução atual utiliza a configuração final do AgentGuard. Os resultados históricos das execuções baseline e final utilizadas na comparação do projeto estão preservados em:

```text
evaluations/agentcore/nova-baseline-results.txt
evaluations/agentcore/nova-final-results.txt
```

A configuração completa do AgentCore Evaluations — incluindo publicação do dataset, configuração dos evaluators, observabilidade, traces e problemas encontrados durante a execução — está documentada em:

```text
evaluations/README.md
```

---

## Executando DeepEval

Para executar a suíte de avaliação com DeepEval:

```powershell
deepeval test run evaluations/deepeval/test_agentguard.py -v
```

A suíte executa os 20 casos do Golden Dataset contra o AgentGuard e aplica as métricas configuradas no projeto:

- **Answer Relevancy** — threshold `>= 0.7`
- **G-Eval de conformidade** — threshold `>= 0.8`
- **Faithfulness** — threshold `>= 0.8`, quando existe `retrieval_context`

A execução atual utiliza a configuração final do AgentGuard. Os resultados históricos estão preservados em:

```text
evaluations/deepeval/nova-baseline-results.txt
evaluations/deepeval/nova-final-results.txt
```

---

## Executando Red Teaming

Os scripts de Red Teaming executam ataques estruturados contra o Harness e persistem as evidências de cada execução.

### Campanha baseline

```powershell
python red-teaming/run_redteam.py
```

### Reteste final

```powershell
python red-teaming/run_redteam_final.py
```

As evidências estão armazenadas em:

```text
red-teaming/results/
red-teaming/final-results/
```

Cada arquivo `RT-XX.json` registra informações da execução correspondente ao ataque, incluindo a resposta do agente e os eventos associados.

> Os scripts representam as campanhas utilizadas no experimento. Os resultados baseline e final já registrados no repositório devem ser utilizados para a comparação apresentada neste projeto.

---

## Principais achados

A campanha baseline revelou cinco grupos principais de problemas:

1. confusão entre categorias de segurança;
2. uso inadequado ou grounding insuficiente do Browser;
3. tratamento inadequado de falhas de ferramenta;
4. aceitação de afirmações e garantias sem evidência;
5. inconsistência no contrato de saída.

Esses achados orientaram o hardening do system prompt.

Após o reteste, as três falhas completas identificadas na baseline deixaram de ocorrer no conjunto avaliado.

Entretanto, permaneceram limitações, principalmente na diferenciação entre `JAILBREAK` e `VAZAMENTO_DE_INFORMACAO`, além de limitações operacionais e de grounding envolvendo ferramentas.

Os findings completos estão disponíveis em:

```text
red-teaming/findings.md
```

---

## Limitações

Os resultados deste projeto devem ser interpretados dentro do conjunto de cenários avaliados.

Entre as limitações observadas estão:

- divergências entre diferentes avaliadores;
- limitações do Browser em algumas execuções;
- erros técnicos do evaluator customizado em cenários com ferramentas;
- conflitos entre helpfulness e comportamento seguro;
- diferenças de pipeline entre algumas execuções do AgentCore;
- persistência de erros de taxonomia na versão final.

O `Builtin.Helpfulness`, por exemplo, possui uma limitação importante neste domínio: uma resposta segura pode deliberadamente não cumprir um objetivo malicioso do usuário. Portanto, maior helpfulness não representa necessariamente maior segurança.

Nenhum resultado apresentado deve ser interpretado como garantia de segurança absoluta.

---

## Documentação adicional

| Documento | Conteúdo |
|---|---|
| `evaluations/README.md` | Configuração e execução do AgentCore Evaluations |
| `evaluations/baseline-vs-final.md` | Comparação consolidada baseline × final |
| `red-teaming/README.md` | Metodologia e execução do Red Teaming |
| `red-teaming/baseline-campaign.md` | Campanha de Red Teaming baseline |
| `red-teaming/final-campaign.md` | Campanha de Red Teaming final |
| `red-teaming/findings.md` | Achados, riscos, correções e validação após hardening |
| `exploratory/baseline-v1.md` | Registro da exploração inicial da baseline |