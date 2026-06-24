# Prompt library

Prompts are versioned assets, not strings scattered through the code. Each `*.yaml` file is
one prompt with an explicit `version`, a description, and `system` / `user` templates.

## Schema

```yaml
name: rag_answer          # must match the filename (rag_answer.yaml)
version: "1.2.0"          # semantic version; bump on any wording change
description: >            # what it does and the behaviour it enforces
  ...
system: |                 # system message template (str.format placeholders)
  ...
user: |                   # user message template
  ... {question} ...
```

## Usage

```python
from ai_core import load_prompt, structured_chat

prompt = load_prompt("rag_answer")
system, user = prompt.render(context=ctx, question=q)
```

## Versioning policy

- **Patch** (`1.2.0 -> 1.2.1`): typo / formatting, no behavioural change.
- **Minor** (`1.2.0 -> 1.3.0`): new guidance or fields, backward compatible.
- **Major** (`1.2.0 -> 2.0.0`): behaviour or output schema change that callers must review.

See [`../../../docs/prompt-engineering.md`](../../../docs/prompt-engineering.md) for the full
approach to structuring, versioning and evaluating prompts.

## Current prompts

| File | Version | Purpose |
|------|---------|---------|
| `rag_answer.yaml` | 1.2.0 | Grounded RAG answering with explicit "I don't know" |
| `intent_classifier.yaml` | 1.1.0 | Support-message intent + routing classification |
| `document_extraction.yaml` | 2.0.0 | Structured field extraction from raw document text |
