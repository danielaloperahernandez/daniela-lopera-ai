# Intent taxonomy & routing

The agent classifies every inbound message into exactly one category and decides whether to
auto-answer or escalate. The classifier prompt is versioned in
[`intent_classifier.yaml`](../../../shared/ai_core/prompts/intent_classifier.yaml).

| Category | Auto-handled? | Action |
|----------|---------------|--------|
| `question` | Yes (if confident) | Answer from the RAG knowledge base |
| `bug_report` | Partly | Acknowledge + escalate to team |
| `billing` | No | Escalate to a human (money-sensitive) |
| `feature_request` | No | Acknowledge + log for product |
| `complaint` | No | Escalate with high priority (churn risk) |
| `other` | No | Escalate when unsure |

## Routing rules (implemented in the Switch node)

1. `escalate == true` -> reply with a holding message **and** notify the human team.
2. `category == question` -> query the knowledge base.
   - If the RAG answer has `answered == true` -> send it.
   - Else -> escalate (don't guess).
3. Anything else -> escalate.

## Why "conservative escalation" matters

The classifier is instructed to set `escalate = true` whenever confidence is low. It is far
cheaper to route an easy question to a human than to confidently send a wrong answer about
billing. This is the kind of guardrail that makes an autonomous flow safe to deploy.

## Fields produced per message

```json
{
  "category": "question",
  "priority": "normal",
  "escalate": false,
  "language": "en"
}
```
