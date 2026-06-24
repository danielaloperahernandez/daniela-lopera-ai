import { skills } from "@/lib/profile";

export function Skills() {
  return (
    <section className="container-tight py-12">
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {skills.map((s) => (
          <div key={s.group}>
            <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
              {s.group}
            </h3>
            <div className="mt-3 flex flex-wrap gap-2">
              {s.items.map((item) => (
                <span key={item} className="pill">
                  {item}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
