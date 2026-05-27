import { useEffect, useState } from "react";

import { fetchHealth } from "../lib/api";

type StatusState =
  | { kind: "loading" }
  | { kind: "success"; message: string }
  | { kind: "error"; message: string };

export default function Home() {
  const [status, setStatus] = useState<StatusState>({ kind: "loading" });

  useEffect(() => {
    let isMounted = true;

    const loadHealth = async () => {
      try {
        const data = await fetchHealth();
        if (isMounted) {
          setStatus({ kind: "success", message: data.status });
        }
      } catch {
        if (isMounted) {
          setStatus({ kind: "error", message: "unreachable" });
        }
      }
    };

    void loadHealth();

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <section className="mx-auto flex min-h-[calc(100vh-81px)] max-w-6xl items-center px-6 py-16">
      <div className="grid gap-10 lg:grid-cols-[1.2fr_0.8fr] lg:items-center">
        <div className="space-y-6">
          <p className="inline-flex rounded-full border border-amber-400/20 bg-amber-300/10 px-4 py-2 text-xs uppercase tracking-[0.25em] text-amber-200">
            Django + React + PostgreSQL
          </p>
          <div className="space-y-4">
            <h2 className="max-w-3xl text-5xl font-bold leading-tight text-sand sm:text-6xl">
              A clean, fast starting point for your next full-stack product.
            </h2>
            <p className="max-w-2xl text-lg leading-8 text-stone-300">
              `proxyfaux` ships with a split Django settings layout, a typed React
              frontend, and development containers tuned for local iteration.
            </p>
          </div>
        </div>

        <div className="rounded-[2rem] border border-white/10 bg-white/5 p-8 shadow-glow backdrop-blur">
          <p className="text-sm uppercase tracking-[0.2em] text-stone-400">Backend status</p>
          <div className="mt-6 flex items-center gap-4">
            <span
              className={`h-4 w-4 rounded-full ${
                status.kind === "success"
                  ? "bg-emerald-400 shadow-[0_0_20px_rgba(52,211,153,0.8)]"
                  : status.kind === "error"
                    ? "bg-rose-400 shadow-[0_0_20px_rgba(251,113,133,0.8)]"
                    : "bg-amber-300 shadow-[0_0_20px_rgba(252,211,77,0.8)]"
              }`}
            />
            <div>
              <p className="text-3xl font-semibold capitalize text-sand">
                {status.kind === "loading" ? "Checking" : status.message}
              </p>
              <p className="mt-2 text-sm text-stone-400">
                {status.kind === "success" &&
                  "The frontend is connected to the Django API."}
                {status.kind === "loading" &&
                  "Calling GET /api/health/ to confirm the stack is live."}
                {status.kind === "error" &&
                  "The API could not be reached. Start the backend or check VITE_API_BASE_URL."}
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

