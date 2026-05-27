import { Outlet } from "react-router-dom";

export default function Layout() {
  return (
    <div className="min-h-screen bg-transparent text-sand">
      <header className="border-b border-white/10">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-amber-300/70">proxyfaux</p>
            <h1 className="text-lg font-semibold">Modern Full-Stack Starter</h1>
          </div>
          <a
            className="rounded-full border border-amber-400/30 px-4 py-2 text-sm text-amber-100 transition hover:border-amber-300 hover:bg-amber-300/10"
            href="http://localhost:8009/api/health/"
            target="_blank"
            rel="noreferrer"
          >
            API health
          </a>
        </div>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
