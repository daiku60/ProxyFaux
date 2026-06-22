import { Outlet } from "react-router-dom";

export default function Layout() {
  return (
    <div className="min-h-screen bg-transparent text-foreground">
      <header className="border-b border-border/70 bg-background/85">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
          <h1 className="text-5xl">Proxyfaux</h1>
        </div>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
