import fs from "fs";
import path from "path";

const rootDir = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..", "..");
const cardsDataPath = path.join(rootDir, "backend", "data", "cards.json");
const backendDataDir = path.join(rootDir, "backend", "data");
const outputDir = path.join(rootDir, "frontend", ".generated");
const outputPath = path.join(outputDir, "language-availability.json");
const variantPattern = /\{([A-Z](?:\|[A-Z])*)\}/;

const rawCatalog = JSON.parse(fs.readFileSync(cardsDataPath, "utf8"));
const allEntries = {
  ...(rawCatalog.models ?? {}),
  ...(rawCatalog.crewCards ?? {}),
  ...(rawCatalog.upgrades ?? {}),
};

const availabilityEntries = Object.fromEntries(
  Object.entries(allEntries).map(([id, entry]) => [id, buildLanguageAvailabilityEntry(entry.pdf)]),
);

fs.mkdirSync(outputDir, { recursive: true });
fs.writeFileSync(outputPath, JSON.stringify(availabilityEntries, null, 2));
console.log(`Wrote ${outputPath}`);

function buildLanguageAvailabilityEntry(pdfPath) {
  if (!pdfPath) {
    return { default: ["en"] };
  }

  const variantMatch = pdfPath.match(variantPattern);
  if (!variantMatch) {
    return { default: collectAvailableLanguages(pdfPath) };
  }

  const variants = variantMatch[1].split("|");
  return {
    default: ["en"],
    variants: Object.fromEntries(
      variants.map((variant) => [
        variant,
        collectAvailableLanguages(pdfPath.replace(variantPattern, variant)),
      ]),
    ),
  };
}

function collectAvailableLanguages(pdfPath) {
  const languages = ["en", "es"].filter((language) =>
    fs.existsSync(path.join(backendDataDir, language, pdfPath)),
  );
  return languages.length > 0 ? languages : ["en"];
}
