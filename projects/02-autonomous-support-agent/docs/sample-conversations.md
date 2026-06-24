# Sample conversations

Illustrative runs showing how the agent classifies, answers, or escalates.

## 1. Answered from the knowledge base

```text
User:  How do I reset my password?
Bot:   Open the login page, click "Forgot password" and enter your account email. You'll get
       a reset link valid for 30 minutes. If it doesn't arrive, check spam.
```

- Intent: `{ category: "question", priority: "normal", escalate: false }`
- RAG: `answered: true` -> the answer is sent directly.

## 2. Escalated (billing)

```text
User:  I was charged twice this month, please refund one.
Bot:   Thanks for reaching out! A human agent will follow up shortly.
```

- Intent: `{ category: "billing", priority: "high", escalate: true }`
- The team also receives an internal Telegram notification with the message and priority.

## 3. Low-confidence question -> escalated, not guessed

```text
User:  Does your Enterprise tier support on-prem deployment in air-gapped networks?
Bot:   Thanks for reaching out! A human agent will follow up shortly.
```

- Intent: `{ category: "question", escalate: false }`
- RAG: `answered: false` (not in the KB) -> the agent escalates instead of hallucinating.

## 4. Complaint -> high-priority escalation

```text
User:  This is the third time the export has failed. I'm done.
Bot:   Thanks for reaching out! A human agent will follow up shortly.
```

- Intent: `{ category: "complaint", priority: "high", escalate: true }`
