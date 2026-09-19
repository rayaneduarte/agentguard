import json
from pathlib import Path

source = Path("datasets/golden-dataset.json")
destination = Path("agentcore/datasets/agentguard_golden.jsonl")

with source.open("r", encoding="utf-8") as file:
    golden = json.load(file)

with destination.open("w", encoding="utf-8") as file:
    for case in golden:
        raw_input = case["input"]

        # Multi-turno
        if isinstance(raw_input, list):
            turns = [
                {
                    "input": turn["content"]
                }
                for turn in raw_input
                if turn["role"] == "user"
            ]

        # Turno único
        else:
            turns = [
                {
                    "input": raw_input
                }
            ]

        scenario = {
            "scenario_id": case["id"],
            "turns": turns,
            "assertions": case["expected_criteria"],
            "expected_trajectory": []
        }

        file.write(
            json.dumps(scenario, ensure_ascii=False) + "\n"
        )

print(f"{len(golden)} cenários convertidos.")
print(f"Arquivo criado: {destination}")