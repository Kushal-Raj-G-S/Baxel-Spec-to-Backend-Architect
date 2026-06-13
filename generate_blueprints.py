import os
import time
import json
from pathlib import Path
from openai import OpenAI

BASE_URL = "https://integrate.api.nvidia.com/v1"
MODEL = "qwen/qwen3-coder-480b-a35b-instruct"

# These are just guardrails to shame the model away from boring defaults.
# NOT a whitelist — the model can still pick anything outside these.
BANNED_BORING_ARCHETYPES = [
    "E-commerce Platform", "Chat Application", "Video Streaming Service",
    "Todo App", "Blog Platform", "Social Media App", "Food Delivery App",
    "Ride Sharing App", "Hotel Booking", "Job Board", "News Aggregator",
    "Generic SaaS Dashboard", "CRM", "Project Management Tool",
]


def _read_env_file_value(key: str) -> str:
    env_file = Path(".env")
    if not env_file.exists():
        return ""
    try:
        lines = env_file.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            left, right = line.split("=", 1)
            if left.strip() == key:
                return right.strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


def _load_api_key() -> str:
    return os.getenv("NVIDIA_API_KEY", "").strip() or _read_env_file_value("NVIDIA_API_KEY")


def clean_json_response(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline:].strip()
        if text.endswith("```"):
            text = text[:-3].strip()
    return text


def build_prompt(already_chosen: list[str], step: int, total: int) -> str:
    exclude_str = "\n".join(f"  - {a}" for a in already_chosen) if already_chosen else "  None yet"
    banned_str  = "\n".join(f"  - {b}" for b in BANNED_BORING_ARCHETYPES)

    return f"""You are a Principal Systems Architect with deep knowledge across every industry vertical — not just tech startups.

Your task: Invent a genuinely UNIQUE and SPECIFIC system archetype for blueprint #{step} of {total}.

━━━ STRICT RULES ━━━
1. DO NOT pick anything in this banned list (overused, boring, not impressive):
{banned_str}

2. DO NOT repeat anything already chosen in this session:
{exclude_str}

3. Your archetype MUST come from an UNEXPECTED or NICHE industry vertical.
   Think: nuclear energy, satellite operations, livestock genetics, courtroom forensics,
   maritime shipping, neuroscience research, underground mining, actuarial modeling,
   pharmaceutical cold chain, carbon trading, esports tournament ops, military logistics,
   rare earth mineral tracing, humanitarian aid distribution, deep-sea cable management —
   or any other industry a typical developer would NEVER think to build for.

4. The archetype must describe a REAL, SPECIFIC software system — not a vague concept.
   BAD example: "Healthcare Platform"
   GOOD example: "Intraoperative Neural Monitoring Alert System for Spinal Surgery"

5. The blueprint must reflect genuine domain complexity — real protocols, compliance
   standards, hardware interfaces, or industry-specific data formats that make this
   system non-trivial to build.

6. Keep all descriptions, rules, anti_patterns, key_technical_challenges, and stack reasons highly concise (1-2 sentences maximum per item) to guarantee the output is not truncated.

━━━ OUTPUT FORMAT ━━━
Output a single raw JSON object. No markdown, no explanation, no preamble.
Start with '{{' and end with '}}'. Strictly follow this schema:

{{
  "archetype": "Specific name of the system",
  "domain": "The industry vertical (be specific, e.g. 'Intraoperative Neuroscience' not just 'Healthcare')",
  "description": "2-3 sentences: what it does, who uses it, what makes it technically hard",
  "rules": [
    "MUST rule 1 — reference real protocols, standards, or domain constraints",
    "MUST rule 2",
    "MUST rule 3",
    "MUST rule 4",
    "MUST rule 5"
  ],
  "anti_patterns": [
    "DO NOT do X — explain why it fails specifically in this domain",
    "DO NOT do Y",
    "DO NOT do Z"
  ],
  "key_technical_challenges": [
    "Hard engineering problem 1 specific to this archetype",
    "Hard engineering problem 2",
    "Hard engineering problem 3"
  ],
  "recommended_stack": {{
    "language": "Language + one-line reason why it fits this domain",
    "framework": "Framework + one-line reason",
    "database_engine": "DB + one-line reason",
    "cache": "Cache layer or null",
    "message_broker": "Broker or null",
    "special_services": ["Domain-specific service 1", "Domain-specific service 2"]
  }},
  "compliance_flags": ["Regulation 1", "Regulation 2"]
}}"""


def main() -> None:
    api_key = _load_api_key()
    if not api_key:
        raise RuntimeError("NVIDIA_API_KEY not found in environment or .env")

    client = OpenAI(base_url=BASE_URL, api_key=api_key)

    outputs_dir = Path(__file__).parent / "outputs"
    model_slug = MODEL.replace("/", "_").replace(":", "_").replace("-", "_")
    model_out_dir = outputs_dir / model_slug
    model_out_dir.mkdir(parents=True, exist_ok=True)

    target_count = 50
    max_attempts_per_slot = 4   # retries per blueprint slot before giving up
    global_max_attempts = 80    # total API calls allowed across the whole run

    print(f"=== Baxel Blueprint Generator (Free-Choice Mode) ===")
    print(f"Model  : {MODEL}")
    print(f"Target : {target_count} unique archetypes\n")

    # Load already generated archetypes (resume support)
    generated_archetypes: list[str] = []

    for f in sorted(model_out_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            arch = data.get("archetype", "")
            if arch:
                generated_archetypes.append(arch)
        except Exception:
            pass

    if generated_archetypes:
        print(f"  Resuming — {len(generated_archetypes)} already generated:")
        for name in generated_archetypes:
            print(f"    v {name}")
        print()

    total_api_calls = 0
    failed_slots = 0

    while len(generated_archetypes) < target_count and total_api_calls < global_max_attempts:
        slot = len(generated_archetypes) + 1
        print(f"  [{slot:02d}/{target_count}] Requesting unique archetype from model...")

        success = False
        for attempt in range(1, max_attempts_per_slot + 1):
            total_api_calls += 1
            try:
                start = time.perf_counter()
                completion = client.chat.completions.create(
                    model=MODEL,
                    messages=[{
                        "role": "user",
                        "content": build_prompt(generated_archetypes, slot, target_count)
                    }],
                    temperature=0.85,
                    max_tokens=2048,
                )
                raw = completion.choices[0].message.content
                if raw is None:
                    raise ValueError("Model returned an empty content or None response")
                elapsed = time.perf_counter() - start

                cleaned = clean_json_response(raw)
                parsed = json.loads(cleaned)

                # Validate required fields
                for key in ("archetype", "domain", "rules", "anti_patterns", "recommended_stack"):
                    if key not in parsed:
                        raise ValueError(f"Missing required key: '{key}'")

                arch_name = parsed["archetype"].strip()
                if not arch_name:
                    raise ValueError("Empty archetype name")

                # Duplicate check (case-insensitive)
                if any(arch_name.lower() == existing.lower() for existing in generated_archetypes):
                    raise ValueError(f"Duplicate archetype: '{arch_name}'")

                # Boring check — warn but don't hard-reject
                if any(banned.lower() in arch_name.lower() for banned in BANNED_BORING_ARCHETYPES):
                    print(f"           ! Model chose a potentially boring archetype: '{arch_name}' — saving anyway")

                # Save to file
                slug = (
                    arch_name.lower()
                    .replace(" ", "_").replace("/", "_").replace("&", "and")
                    .replace("-", "_").replace(",", "").replace("(", "").replace(")", "")
                    .replace("'", "").replace(":", "")
                )[:80]
                out_file = model_out_dir / f"{slot:02d}_{slug}.json"
                out_file.write_text(json.dumps(parsed, indent=2), encoding="utf-8")

                generated_archetypes.append(arch_name)
                print(f"           + '{arch_name}' [{parsed.get('domain', '?')}] — {elapsed:.2f}s")
                success = True
                break

            except json.JSONDecodeError as e:
                print(f"           x Attempt {attempt}/{max_attempts_per_slot} — JSON parse error: {e}")
                if 'raw' in locals() and raw:
                    print(f"             Raw response snippet: {raw[:300]!r} ... {raw[-300:]!r}")
            except ValueError as e:
                print(f"           x Attempt {attempt}/{max_attempts_per_slot} — {e}")
            except Exception as e:
                print(f"           x Attempt {attempt}/{max_attempts_per_slot} — Unexpected: {e}")

            if attempt < max_attempts_per_slot:
                time.sleep(2.0)

        if not success:
            failed_slots += 1
            print(f"           x GAVE UP on slot {slot} after {max_attempts_per_slot} attempts\n")
            if failed_slots >= 5:
                print("  Too many consecutive failures — aborting run.")
                break

        time.sleep(1.0)

    # Summary
    print(f"\n{'='*50}")
    print(f"  Generated : {len(generated_archetypes)}/{target_count} blueprints")
    print(f"  API calls : {total_api_calls}")
    print(f"  Output    : {model_out_dir.resolve()}")
    if len(generated_archetypes) < target_count:
        print(f"  Run again to resume from #{len(generated_archetypes)+1}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
