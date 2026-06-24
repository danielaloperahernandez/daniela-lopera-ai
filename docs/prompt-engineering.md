# Prompt engineering: structure, versioning, optimization

Prompts in this portfolio are treated as **engineering artifacts**, not magic strings. They
live in YAML files, carry semantic versions, and are exercised by the evaluation harness.
This document explains the approach a technical reviewer would want to see.

## 1. Where prompts live

All prompts are in [`shared/ai_core/prompts/`](../shared/ai_core/prompts) as versioned YAML:

```yaml
name: rag_answer
version: "1.2.0"
description: >
  Grounded RAG answering with explicit "I don't know".
system: |
  ...
user: |
  ... {question} ...
```

They are loaded with `load_prompt("rag_answer")` and rendered with `.render(**kwargs)`.
Keeping them out of code means a prompt change is a small, reviewable diff, not a hunt
through Python files.

## 2. How they're structured

Each prompt follows the same skeleton:

1. **Role** - who the model is ("a precise knowledge-base assistant").
2. **Task** - exactly what to produce.
3. **Hard rules** - the guardrails that matter, stated as imperatives:
   - "Answer ONLY from the context."
   - "If not in context, reply exactly: 'I don't have enough information...'."
   - "Do not guess or hallucinate."
4. **Output contract** - paired with Pydantic schemas via `with_structured_output`, so the
   model returns validated JSON rather than prose we have to parse.

## 3. Versioning policy

Semantic versioning per prompt:

| Change | Bump | Example |
|--------|------|---------|
| Typo / formatting | patch | `1.2.0 -> 1.2.1` |
| New guidance, backward compatible | minor | `1.2.0 -> 1.3.0` |
| Behaviour / output-schema change | major | `1.2.0 -> 2.0.0` |

Because the version travels with the prompt, you can tie an evaluation run to the exact
prompt version that produced it.

## 4. Structured output over parsing

Every LLM call that needs machine-readable output uses `structured_chat(Schema, ...)`,
which:

- forces the provider to return JSON matching a Pydantic model,
- retries transient rate-limit / timeout / overloaded errors with exponential backoff,
- works identically across OpenAI, Anthropic and Gemini.

This removes a whole class of brittle "regex the model's prose" bugs.

## 5. Optimization loop

Prompts are improved with evidence, not vibes:

1. Write a small **golden dataset** (see
   [`projects/03-rag-engine/eval/dataset.jsonl`](../projects/03-rag-engine/eval/dataset.jsonl)).
2. Run the **evaluation harness** to score correctness, faithfulness and abstention.
3. Change one thing in the prompt, bump the version, re-run, compare.
4. Keep the change only if the metrics improve.

The two highest-leverage techniques used here:

- **Explicit abstention** - telling the model to say "I don't know" measurably raises
  faithfulness and is what makes the autonomous agent safe (it escalates instead of guessing).
- **Grounding by delimiter** - wrapping retrieved context in `<context>...</context>` and
  instructing the model to use only what's inside reduces drift to parametric memory.

## 6. Per-provider notes

- Temperature is kept low (0.0-0.1) for classification and extraction to maximize
  determinism.
- Anthropic has no embeddings API; the core transparently falls back to OpenAI embeddings.
- JSON mode / structured output is requested through LangChain so the same code path works
  for all three providers.
