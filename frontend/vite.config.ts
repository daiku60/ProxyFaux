import path from "path";
import fs from "fs";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

function resolveCardsDataPath(): string {
  const candidates = [
    path.resolve(__dirname, "../backend/data/cards.json"),
    path.resolve(__dirname, "backend-data/cards.json"),
  ];

  const match = candidates.find((candidate) => fs.existsSync(candidate));
  if (!match) {
    throw new Error(
      `Could not find cards.json. Checked: ${candidates.join(", ")}`,
    );
  }

  return match;
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const basePath = env.VITE_BASE_PATH || "/";
  const workspaceRoot = path.resolve(__dirname, "..");
  const cardsDataPath = resolveCardsDataPath();

  if (mode === "prod" && !env.VITE_API_BASE_URL) {
    throw new Error("VITE_API_BASE_URL must be set for prod builds.");
  }

  // Ensure base path starts with slash and ends with slash.
  const normalizedBasePath = basePath.startsWith("/") ? basePath : `/${basePath}`;
  const finalBasePath = normalizedBasePath.endsWith("/")
    ? normalizedBasePath
    : `${normalizedBasePath}/`;

  return {
    plugins: [react()],
    base: finalBasePath,
    server: {
      fs: {
        allow: [workspaceRoot],
      },
      host: "0.0.0.0",
      port: 6174,
    },
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "src"),
        "@cards-data": cardsDataPath,
      },
    },
    build: {
      outDir: "dist",
      assetsDir: ".",
      rollupOptions: {
        output: {
          entryFileNames: "index.js",
          assetFileNames: (assetInfo) =>
            assetInfo.name?.endsWith(".css") ? "index.css" : "assets/[name][extname]",
        },
      },
    },
  };
});
