import Link from "next/link";
import { profile } from "@/lib/profile";

export function Nav() {
  return (
    <header className="sticky top-0 z-20 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur">
      <nav className="container-tight flex h-16 items-center justify-between">
        <Link href="/" className="font-mono text-sm font-semibold text-slate-100">
          {profile.name}
          <span className="text-brand">.dev</span>
        </Link>
        <div className="flex items-center gap-6 text-sm text-slate-300">
          <Link href="/#projects" className="hover:text-white">
            Projects
          </Link>
          <Link href="/#about" className="hover:text-white">
            About
          </Link>
          <a
            href={profile.links.github}
            target="_blank"
            rel="noreferrer"
            className="hover:text-white"
          >
            GitHub
          </a>
          <a
            href={`mailto:${profile.email}`}
            className="rounded-lg bg-brand px-3 py-1.5 font-medium text-white hover:bg-brand-soft"
          >
            Contact
          </a>
        </div>
      </nav>
    </header>
  );
}
