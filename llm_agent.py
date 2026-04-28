"""
LLM design agent — uses a local Ollama model to propose aerodynamic changes.

The agent receives:
  - F1 2026 regulation excerpts (parsed from the PDF)
  - Current design parameters
  - History of past designs and their CFD scores

It returns a JSON proposal with two variants: conservative and aggressive.
"""

import json
import re
from pathlib import Path

import fitz  # PyMuPDF
import ollama

from rule_checker import DEFAULT_PARAMS, LIMITS

MODEL = "qwen2.5:14b"  # change to llama3.1:8b for faster but weaker reasoning

SYSTEM_PROMPT = Path("prompts/design_agent.txt").read_text()


def extract_pdf_text(pdf_path: Path, max_chars: int = 40_000) -> str:
    """Extract text from the F1 rulebook PDF, truncated to fit LLM context."""
    doc = fitz.open(str(pdf_path))
    chunks = []
    total = 0
    for page in doc:
        text = page.get_text()
        chunks.append(text)
        total += len(text)
        if total >= max_chars:
            break
    return "\n".join(chunks)[:max_chars]


class DesignAgent:
    def __init__(self, rulebook_path: Path, model: str = MODEL):
        self.model = model
        print(f"Loading rulebook: {rulebook_path}")
        self.rules_text = extract_pdf_text(rulebook_path)
        print(f"  Extracted {len(self.rules_text):,} chars from rulebook")
        self._verify_ollama()

    def _verify_ollama(self) -> None:
        try:
            ollama.show(self.model)
        except Exception:
            raise RuntimeError(
                f"Model '{self.model}' not found in Ollama.\n"
                f"Run: ollama pull {self.model}"
            )

    def _history_summary(self, history: list, max_entries: int = 10) -> str:
        if not history:
            return "No previous iterations yet."
        recent = history[-max_entries:]
        lines = []
        for h in recent:
            lines.append(
                f"  iter={h['iteration']} variant={h['variant']} "
                f"score={h['score']:.3f} "
                f"CL={h['results']['cl']:.4f} CD={h['results']['cd']:.4f} "
                f"params={json.dumps(h['params']['parameters'])}"
            )
        return "\n".join(lines)

    def propose(self, current_params: dict, history: list) -> dict:
        """
        Ask the LLM for two design variants based on history.
        Returns: {"variant_a": {params, reasoning}, "variant_b": {params, reasoning}}
        """
        param_bounds = {
            k: {"min": v["min"], "max": v["max"]}
            for k, v in LIMITS.items()
        }

        user_msg = f"""
Current design parameters:
{json.dumps(current_params, indent=2)}

Parameter legal limits:
{json.dumps(param_bounds, indent=2)}

Recent design history (newest last):
{self._history_summary(history)}

F1 2026 Technical Regulation excerpts:
{self.rules_text[:8000]}

Propose two design variants to improve aerodynamic efficiency (maximize CL/CD).
Variant A should be a conservative refinement.
Variant B should be a bolder change targeting higher downforce.

Respond ONLY with valid JSON in exactly this structure:
{{
  "variant_a": {{
    "reasoning": "...",
    "regulation_basis": "Art. X.X.X allows ...",
    "parameters": {{
      "front_wing_main_angle": 0.0,
      "front_wing_flap_angle": 0.0,
      "rear_wing_main_angle": 0.0,
      "rear_wing_beam_angle": 0.0,
      "front_ride_height": 0.0,
      "rear_ride_height": 0.0,
      "diffuser_angle": 0.0,
      "diffuser_exit_height": 0.0,
      "floor_edge_height": 0.0
    }}
  }},
  "variant_b": {{
    "reasoning": "...",
    "regulation_basis": "Art. X.X.X allows ...",
    "parameters": {{ ... }}
  }}
}}
"""
        response = ollama.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            options={"temperature": 0.4},
        )
        raw = response["message"]["content"]
        return self._parse_response(raw, current_params)

    def _parse_response(self, raw: str, fallback_params: dict) -> dict:
        # Strip markdown code fences if present
        raw = re.sub(r"```(?:json)?", "", raw).strip()
        try:
            data = json.loads(raw)
            # Validate expected keys
            for key in ("variant_a", "variant_b"):
                if key not in data or "parameters" not in data[key]:
                    raise ValueError(f"Missing '{key}.parameters' in LLM response")
            return data
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[llm_agent] Failed to parse LLM response ({e}), using fallback params")
            return {
                "variant_a": {"reasoning": "parse error fallback", "regulation_basis": "", "parameters": fallback_params},
                "variant_b": {"reasoning": "parse error fallback", "regulation_basis": "", "parameters": fallback_params},
            }
