import Link from "next/link";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Nav } from "@/components/Nav";
import { Footer } from "@/components/Footer";
import { getProject, projects } from "@/lib/projects";
import { profile } from "@/lib/profile";

export function generateStaticParams() {
  return projects.map((p) => ({ slug: p.slug }));
}

export function generateMetadata({
  params,
}: {
  params: { slug: string };
}): Metadata {
  const project = getProject(params.slug);
  if (!project) return {};
  return {
    title: `${project.title} - ${profile.name}`,
    description: project.summary,
  };
}

export default function ProjectPage({ params }: { params: { slug: string } }) {
  const project = getProject(params.slug);
  if (!project) notFound();

  const repoUrl = `${profile.links.github}/tree/main/${project.repoPath}`;

  return (
    <>
      <Nav />
      <main className="container-tight py-16">
        <Link href="/#projects" className="text-sm text-slate-400 hover:text-white">
          &lt;- Back to projects
        </Link>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <span className="font-mono text-sm text-brand-soft">{project.number}</span>
          <span className="pill">{project.kind}</span>
        </div>
        <h1 className="mt-3 text-4xl font-bold text-white">{project.title}</h1>
        <p className="mt-4 max-w-2xl text-lg text-slate-300">{project.summary}</p>

        <div className="mt-6 flex flex-wrap gap-2">
          {project.stack.map((tech) => (
            <span key={tech} className="pill">
              {tech}
            </span>
          ))}
        </div>

        <div className="mt-8 grid gap-8 lg:grid-cols-2">
          <section className="card">
            <h2 className="text-lg font-semibold text-white">The problem</h2>
            <p className="mt-3 text-slate-300">{project.problem}</p>
            <h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-slate-400">
              What it proves
            </h3>
            <p className="mt-2 text-slate-300">{project.proves}</p>
          </section>

          <section className="card">
            <h2 className="text-lg font-semibold text-white">Architecture</h2>
            <ol className="mt-3 space-y-2">
              {project.architecture.map((step, i) => (
                <li key={i} className="flex gap-3 text-slate-300">
                  <span className="font-mono text-sm text-brand-soft">{i + 1}.</span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          </section>
        </div>

        {project.image && (
          <section className="card mt-8">
            <h2 className="text-lg font-semibold text-white">Architecture diagram</h2>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={project.image}
              alt={`${project.title} architecture diagram`}
              className="mt-4 w-full rounded-xl border border-slate-800"
            />
          </section>
        )}

        <section className="card mt-8">
          <h2 className="text-lg font-semibold text-white">Engineering highlights</h2>
          <ul className="mt-3 grid gap-2 sm:grid-cols-2">
            {project.highlights.map((h) => (
              <li key={h} className="flex gap-2 text-slate-300">
                <span className="text-brand-soft">+</span>
                <span>{h}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="card mt-8 border-dashed">
          <h2 className="text-lg font-semibold text-white">Demo</h2>
          <p className="mt-2 text-slate-400">{project.demoNote}</p>
          <div className="mt-4 flex aspect-video items-center justify-center rounded-xl border border-slate-800 bg-slate-950/60 text-sm text-slate-500">
            Demo recording placeholder (add a Loom link or demo.gif)
          </div>
        </section>

        <div className="mt-8 flex flex-wrap gap-3">
          <a
            href={repoUrl}
            target="_blank"
            rel="noreferrer"
            className="rounded-lg bg-brand px-5 py-2.5 font-medium text-white hover:bg-brand-soft"
          >
            View the code
          </a>
          <a
            href={`mailto:${profile.email}`}
            className="rounded-lg border border-slate-700 px-5 py-2.5 font-medium text-slate-200 hover:border-slate-500"
          >
            Get in touch
          </a>
        </div>
      </main>
      <Footer />
    </>
  );
}
