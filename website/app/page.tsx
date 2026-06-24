import { Nav } from "@/components/Nav";
import { Hero } from "@/components/Hero";
import { Skills } from "@/components/Skills";
import { ProjectCard } from "@/components/ProjectCard";
import { Footer } from "@/components/Footer";
import { profile } from "@/lib/profile";
import { projects } from "@/lib/projects";

export default function HomePage() {
  return (
    <>
      <Nav />
      <main>
        <Hero />
        <Skills />

        <section id="projects" className="container-tight py-16">
          <div className="mb-8">
            <h2 className="text-2xl font-bold text-white">Featured projects</h2>
            <p className="mt-2 max-w-2xl text-slate-400">
              Deep, runnable projects, not tutorials. Each shows when to use n8n for speed and
              when to use Python for complex logic.
            </p>
          </div>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {projects.map((project) => (
              <ProjectCard key={project.slug} project={project} />
            ))}
          </div>
        </section>

        <section id="about" className="container-tight py-16">
          <h2 className="text-2xl font-bold text-white">About</h2>
          <div className="mt-4 max-w-3xl space-y-4 text-slate-300">
            {profile.about.map((p, i) => (
              <p key={i}>{p}</p>
            ))}
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
