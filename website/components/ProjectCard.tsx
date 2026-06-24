import Link from "next/link";
import type { Project } from "@/lib/projects";

export function ProjectCard({ project }: { project: Project }) {
  return (
    <Link href={`/projects/${project.slug}`} className="card group block">
      <div className="flex items-center justify-between">
        <span className="font-mono text-sm text-brand-soft">{project.number}</span>
        <span className="pill">{project.kind}</span>
      </div>
      <h3 className="mt-4 text-xl font-semibold text-white group-hover:text-brand-soft">
        {project.title}
      </h3>
      <p className="mt-2 text-sm leading-relaxed text-slate-400">{project.summary}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        {project.stack.slice(0, 4).map((tech) => (
          <span key={tech} className="pill">
            {tech}
          </span>
        ))}
      </div>
      <span className="mt-5 inline-block text-sm font-medium text-brand-soft">
        Read the case study -&gt;
      </span>
    </Link>
  );
}
