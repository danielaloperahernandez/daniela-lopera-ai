import { profile } from "@/lib/profile";

export function Hero() {
  return (
    <section className="relative overflow-hidden">
      <div
        className="pointer-events-none absolute inset-0 -z-10 opacity-40"
        style={{
          background:
            "radial-gradient(40rem 20rem at 50% -10%, rgba(99,102,241,0.35), transparent)",
        }}
      />
      <div className="container-tight py-24 sm:py-32">
        <p className="font-mono text-sm text-brand-soft">{profile.title}</p>
        <h1 className="mt-4 max-w-3xl text-4xl font-bold leading-tight text-white sm:text-6xl">
          {profile.name}
        </h1>
        <p className="mt-6 max-w-2xl text-lg text-slate-300">{profile.tagline}</p>
        <div className="mt-8 flex flex-wrap gap-3">
          <a
            href="#projects"
            className="rounded-lg bg-brand px-5 py-2.5 font-medium text-white hover:bg-brand-soft"
          >
            View projects
          </a>
          <a
            href={profile.links.github}
            target="_blank"
            rel="noreferrer"
            className="rounded-lg border border-slate-700 px-5 py-2.5 font-medium text-slate-200 hover:border-slate-500"
          >
            GitHub
          </a>
          <a
            href={profile.links.linkedin}
            target="_blank"
            rel="noreferrer"
            className="rounded-lg border border-slate-700 px-5 py-2.5 font-medium text-slate-200 hover:border-slate-500"
          >
            LinkedIn
          </a>
        </div>
      </div>
    </section>
  );
}
