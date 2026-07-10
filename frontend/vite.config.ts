import path from "path";
import fs from "fs";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

const VARIANT_PATTERN = /\{([A-Z](?:\|[A-Z])*)\}/;

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

function resolveLanguageAvailabilityPath(cardsDataPath: string): string {
  const backendDataDir = path.resolve(path.dirname(cardsDataPath));
  const outputDir = path.resolve(__dirname, ".generated");
  const outputPath = path.join(outputDir, "language-availability.json");
  const rawCatalog = JSON.parse(fs.readFileSync(cardsDataPath, "utf8")) as {
    crewCards?: Record<string, { pdf?: string }>;
    models?: Record<string, { pdf?: string }>;
    upgrades?: Record<string, { pdf?: string }>;
  };
  const availabilityEntries = Object.fromEntries(
    Object.entries({
      ...(rawCatalog.models ?? {}),
      ...(rawCatalog.crewCards ?? {}),
      ...(rawCatalog.upgrades ?? {}),
    }).map(([id, entry]) => [id, buildLanguageAvailabilityEntry(entry.pdf, backendDataDir)]),
  );

  fs.mkdirSync(outputDir, { recursive: true });
  fs.writeFileSync(outputPath, JSON.stringify(availabilityEntries, null, 2));
  return outputPath;
}

function buildLanguageAvailabilityEntry(
  pdfPath: string | undefined,
  backendDataDir: string,
): {
  default: string[];
  variants?: Record<string, string[]>;
} {
  if (!pdfPath) {
    return { default: ["en"] };
  }

  const variantMatch = pdfPath.match(VARIANT_PATTERN);
  if (!variantMatch) {
    return { default: collectAvailableLanguages(pdfPath, backendDataDir) };
  }

  const variants = variantMatch[1].split("|");
  return {
    default: ["en"],
    variants: Object.fromEntries(
      variants.map((variant) => [
        variant,
        collectAvailableLanguages(pdfPath.replace(VARIANT_PATTERN, variant), backendDataDir),
      ]),
    ),
  };
}

function collectAvailableLanguages(pdfPath: string, backendDataDir: string): string[] {
  const languages = ["en", "es"].filter((language) =>
    fs.existsSync(path.join(backendDataDir, language, pdfPath)),
  );

  return languages.length > 0 ? languages : ["en"];
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const basePath = env.VITE_BASE_PATH || "/";
  const workspaceRoot = path.resolve(__dirname, "..");
  const cardsDataPath = resolveCardsDataPath();
  const languageAvailabilityPath = resolveLanguageAvailabilityPath(cardsDataPath);

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
        "@language-availability": languageAvailabilityPath,
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
