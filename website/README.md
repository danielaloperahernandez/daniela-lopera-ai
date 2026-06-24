# Portfolio website

The recruiter-facing showcase for the three projects in this repo. Built with **Next.js
(App Router) + TypeScript + Tailwind CSS**, designed to be understood in five minutes and
deployed to Vercel.

## What's here

- A hero with name, title and value proposition.
- A skills overview and an "About" section.
- A projects grid linking to a detail page per project (problem, architecture, highlights,
  demo placeholder, and a "View the code" link).
- Dark mode by default, responsive, with SEO/OpenGraph metadata.

## Requirements

> **Node.js 18.17+ is required** (Next.js 14). Check with `node --version`.

## Run locally

```bash
cd website
npm install
npm run dev        # http://localhost:3000
```

## Build

```bash
npm run build
npm run start
```

## Customize

All content lives in two data files, so you rarely touch the components:

- [`lib/profile.ts`](lib/profile.ts) - your name, title, tagline, links, skills, about.
- [`lib/projects.ts`](lib/projects.ts) - the three project case studies.

Replace the placeholder name, email and GitHub/LinkedIn URLs, then add your real demo links
(Loom) or drop a `demo.gif` and reference it on the project detail pages.

## Deploy to Vercel

1. Push this repo to GitHub.
2. In Vercel, "Import Project" and set the **root directory** to `website/`.
3. Deploy. Vercel auto-detects Next.js; no extra configuration needed.

## Structure

```text
website/
├── app/
│   ├── layout.tsx              # metadata + global shell
│   ├── page.tsx                # home (hero, skills, projects, about)
│   ├── globals.css             # Tailwind layers + small component classes
│   └── projects/[slug]/page.tsx# per-project case study (static generated)
├── components/                 # Nav, Hero, Skills, ProjectCard, Footer
└── lib/                        # profile + projects content (edit these)
```
