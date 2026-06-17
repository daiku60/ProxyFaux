import path from "path";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const basePath = env.VITE_BASE_PATH || "/";
  const workspaceRoot = path.resolve(__dirname, "..");

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
        "@cards-data": path.resolve(__dirname, "../backend/data/cards.json"),
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
