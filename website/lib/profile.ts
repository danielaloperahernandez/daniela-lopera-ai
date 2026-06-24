export const profile = {
  name: "Daniela Lopera",
  title: "AI Developer / AI Automation Engineer",
  tagline:
    "I connect AI models to real operations with Python and n8n: clean code, well-thought workflows, measurable results.",
  location: "Remote",
  email: "danielaloperahernandez@gmail.com",
  links: {
    github: "https://github.com/danielaloperahernandez",
    linkedin: "https://www.linkedin.com/in/daniela-lopera-hernandez/",
  },
  about: [
    "I build hybrid automation: Python for the complex logic (APIs, RAG, data processing) and n8n for fast, reliable orchestration. I reach for each tool where it's strongest instead of forcing everything into one.",
    "My focus is honest engineering: real implementations, grounded AI that doesn't hallucinate, structured outputs, retries and error handling, and prompts that are versioned and evaluated, not guessed.",
  ],
};

export const skills: { group: string; items: string[] }[] = [
  { group: "Languages", items: ["Python", "TypeScript", "SQL"] },
  { group: "AI / LLM", items: ["LangChain", "RAG", "OpenAI", "Anthropic", "Gemini", "Prompt engineering", "Evaluation"] },
  { group: "Automation", items: ["n8n", "Webhooks/APIs", "Error handling", "Telegram / Email"] },
  { group: "Backend & Data", items: ["FastAPI", "Qdrant", "Postgres", "Pydantic"] },
  { group: "Infra", items: ["Docker", "docker-compose", "Vercel"] },
];
