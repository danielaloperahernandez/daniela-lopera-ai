import { profile } from "@/lib/profile";

export function Footer() {
  return (
    <footer id="contact" className="border-t border-slate-800/80 py-12">
      <div className="container-tight flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <p className="font-semibold text-white">{profile.name}</p>
          <p className="text-sm text-slate-400">{profile.title}</p>
        </div>
        <div className="flex gap-6 text-sm text-slate-300">
          <a href={`mailto:${profile.email}`} className="link-underline">
            Email
          </a>
          <a href={profile.links.github} target="_blank" rel="noreferrer" className="link-underline">
            GitHub
          </a>
          <a href={profile.links.linkedin} target="_blank" rel="noreferrer" className="link-underline">
            LinkedIn
          </a>
        </div>
      </div>
    </footer>
  );
}
