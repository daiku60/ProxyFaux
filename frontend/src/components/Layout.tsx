import { Outlet } from "react-router-dom";

export default function Layout() {
  return (
    <div className="min-h-screen bg-transparent text-foreground">
      <header className="border-b border-border/70 bg-background/50 backdrop-blur-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-primary/70">proxyfaux</p>
            <h1 className="font-serif text-2xl font-semibold">Crew Sheet Workshop</h1>
          </div>
          <a
            className="rounded-full border border-border bg-card/70 px-4 py-2 text-sm text-foreground transition hover:bg-secondary"
            href="https://www.wyrd-games.net/"
            target="_blank"
            rel="noreferrer"
          >
            Malifaux reference
          </a>
        </div>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
