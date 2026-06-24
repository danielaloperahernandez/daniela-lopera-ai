export type Project = {
  slug: string;
  number: string;
  title: string;
  kind: string;
  summary: string;
  problem: string;
  proves: string;
  architecture: string[];
  stack: string[];
  highlights: string[];
  repoPath: string;
  demoNote: string;
  image?: string;
};

export const projects: Project[] = [
  {
    slug: "document-intelligence",
    number: "01",
    title: "Document Intelligence",
    kind: "Hybrid - Python + n8n",
    summary:
      "A FastAPI microservice extracts structured data from PDF invoices; n8n orchestrates the business flow over an authenticated API.",
    problem:
      "A company receives invoices as PDF email attachments and wants them as clean, structured rows in a database, automatically. The parsing + schema-constrained LLM extraction is too complex for n8n alone.",
    proves:
      "Knowing when to escape n8n's visual limits with robust code, and connecting the two cleanly over an authenticated HTTP API.",
    architecture: [
      "n8n Email Trigger downloads the PDF attachment",
      "HTTP node POSTs the file to the Python FastAPI service (with retries + x-api-key auth)",
      "FastAPI extracts text (pypdf) and parses it into a validated Pydantic schema via an LLM",
      "n8n stores the structured result in Postgres and sends a Telegram confirmation",
      "A dedicated Error Trigger workflow alerts + logs any failure",
    ],
    stack: ["FastAPI", "pypdf", "LangChain", "n8n", "Postgres", "Docker"],
    highlights: [
      "Validated structured JSON output (no free-text parsing)",
      "Authenticated API + 10MB cap + clean error envelopes",
      "Node-level retries and a central Error Trigger workflow",
    ],
    repoPath: "projects/01-document-intelligence",
    demoNote: "Demo: email in -> structured row in Postgres + Telegram confirmation.",
    image: "/diagrams/document-intelligence-flow.png",
  },
  {
    slug: "autonomous-support-agent",
    number: "02",
    title: "Autonomous Support Agent",
    kind: "Advanced n8n - Telegram",
    summary:
      "A Telegram agent that classifies intent with an LLM, answers from a RAG knowledge base, and escalates sensitive cases to a human.",
    problem:
      "Support inboxes mix repetitive questions with things that genuinely need a human (billing, complaints). Everything should be triaged automatically before a person looks at it.",
    proves:
      "Handling real autonomous business flows safely: grounded answers, conservative escalation, and production error handling.",
    architecture: [
      "Telegram Trigger receives each message",
      "LLM classifies intent into a fixed taxonomy (JSON mode)",
      "A Switch routes: questions go to the RAG knowledge base, sensitive cases escalate",
      "If the RAG answer isn't confident, the agent escalates instead of guessing",
      "Error Trigger workflow alerts the team if anything fails after retries",
    ],
    stack: ["n8n", "Telegram", "OpenAI", "RAG Engine API", "Qdrant"],
    highlights: [
      "Conservative escalation: never guesses on billing/complaints",
      "Grounded answers only (answered=false -> escalate)",
      "Versioned intent-classification prompt + full error handling",
    ],
    repoPath: "projects/02-autonomous-support-agent",
    demoNote: "Demo: question answered from KB; refund request escalated to the team.",
    image: "/diagrams/autonomous-support-agent-flow.png",
  },
  {
    slug: "rag-engine",
    number: "03",
    title: "RAG Engine",
    kind: "Pure Python + Evaluation",
    summary:
      "A retrieval-augmented generation pipeline with grounded structured output, provider-agnostic models, and a real evaluation harness.",
    problem:
      "LLMs hallucinate and can't answer questions about private documents. Answers must be grounded in retrieved context, and quality must be measured, not assumed.",
    proves:
      "Hard AI engineering: retrieval, structured generation, rate-limit handling, and evaluation with correctness / faithfulness / abstention metrics.",
    architecture: [
      "Documents are chunked (800/120) and embedded into Qdrant",
      "A question is embedded and the top-k chunks are retrieved",
      "A grounded prompt forces answers from context, or an explicit 'I don't know'",
      "Output is a validated object: answer + answered + confidence + sources",
      "An eval harness scores correctness, faithfulness and abstention on a golden set",
    ],
    stack: ["Python", "LangChain", "Qdrant", "Pydantic", "Ragas-ready"],
    highlights: [
      "Provider-agnostic core: swap OpenAI/Anthropic/Gemini via one env var",
      "Structured, grounded output with retries on rate limits",
      "Evaluation harness with a golden dataset and LLM-as-judge metrics",
    ],
    repoPath: "projects/03-rag-engine",
    demoNote: "Demo: grounded answer with sources; out-of-scope question abstains.",
    image: "/diagrams/rag-engine-flow.png",
  },
  {
    slug: "manoexperta-voice-agent",
    number: "04",
    title: "ManoExperta Voice Agent",
    kind: "Voice AI - Vapi + n8n",
    summary:
      "A production-style phone agent for a maintenance company: gives safe technical guidance from a knowledge base and books, reschedules and cancels appointments end to end.",
    problem:
      "Staffing a maintenance phone line 24/7 is expensive and inconsistent. The agent must triage issues, advise safely, and manage appointments without ever confirming a booking the system didn't actually commit.",
    proves:
      "Building a stateful, tool-using voice agent backed by correctness-critical logic: a DB concurrency lock, calendar sync, and a fault-tolerance layer that keeps the call alive.",
    architecture: [
      "Vapi handles speech and tool calling, driven by a strict system prompt",
      "n8n receives tool-call webhooks and routes them (RAG vs appointment actions)",
      "consultar_manual_rag retrieves safe procedures from Pinecone (Gemini embeddings)",
      "gestionar_agenda_db books with an ON CONFLICT slot lock + Google Calendar sync",
      "Every external call has a controlled fallback, plus error logging and Telegram alerts",
    ],
    stack: ["Vapi", "n8n", "Pinecone", "Postgres", "Google Calendar", "Telegram"],
    highlights: [
      "Anti-double-booking via a Postgres ON CONFLICT lock",
      "Book-before-cancel reschedule so a client is never left without an appointment",
      "Full fault-tolerance layer: controlled spoken fallbacks + structured audit logs",
      "Returning callers recognized automatically by phone number",
    ],
    repoPath: "projects/04-manoexperta-voice-agent",
    demoNote: "Demo: a call that gives a safe tip, books a visit, then cancels it on a callback.",
    image: "/diagrams/manoexperta-voice-flow.png",
  },
];

export function getProject(slug: string): Project | undefined {
  return projects.find((p) => p.slug === slug);
}
