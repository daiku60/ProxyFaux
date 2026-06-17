import cardsData from "@cards-data";

export type SheetSize = "a4" | "letter";

type CardVersion = {
  displayName?: string;
  front?: string;
};

type CardFiles = {
  defaultBack?: string;
  versions?: CardVersion[];
};

type RawCatalogModel = {
  faction?: string;
  files?: CardFiles;
  name?: string;
  title?: string;
};

type RawCatalog = {
  models?: Record<string, RawCatalogModel>;
};

export type PreviewCard = {
  frontPath: string;
  id: string;
  label: string;
};

type CatalogEntry = {
  fronts: string[];
  id: string;
  label: string;
  title?: string;
};

const catalog = buildCatalog((cardsData as RawCatalog).models ?? {});

export function parseRosterPreview(text: string): PreviewCard[] {
  const previews: PreviewCard[] = [];
  const counters = new Map<string, number>();

  for (const rawLine of text.split("\n")) {
    const cleanedLine = cleanInputLine(rawLine);
    if (!cleanedLine) {
      continue;
    }

    const entry = resolveEntry(cleanedLine);
    if (!entry || entry.fronts.length === 0) {
      continue;
    }

    const currentIndex = counters.get(entry.id) ?? 0;
    const frontPath = entry.fronts[Math.min(currentIndex, entry.fronts.length - 1)];
    counters.set(entry.id, currentIndex + 1);

    previews.push({
      frontPath,
      id: `${entry.id}-${currentIndex}`,
      label: entry.label,
    });
  }

  return previews;
}

function buildCatalog(models: Record<string, RawCatalogModel>): Map<string, CatalogEntry> {
  const lookup = new Map<string, CatalogEntry>();

  for (const [id, model] of Object.entries(models)) {
    const fronts = (model.files?.versions ?? [])
      .map((version) => version.front)
      .filter((frontPath): frontPath is string => typeof frontPath === "string" && frontPath.length > 0);
    if (fronts.length === 0 || !model.name) {
      continue;
    }

    const label = model.title ? `${model.name}, ${model.title}` : model.name;
    const entry: CatalogEntry = {
      fronts,
      id,
      label,
      title: model.title,
    };

    for (const candidate of buildCandidates(model)) {
      const normalized = normalize(candidate);
      if (normalized && !lookup.has(normalized)) {
        lookup.set(normalized, entry);
      }
    }
  }

  return lookup;
}

function buildCandidates(model: RawCatalogModel): string[] {
  const candidates: string[] = [];
  if (model.files?.versions) {
    for (const version of model.files.versions) {
      if (typeof version.displayName === "string" && version.displayName.trim()) {
        candidates.push(version.displayName.trim());
      }
    }
  }
  if (model.name && model.title) {
    candidates.push(`${model.name}, ${model.title}`);
    candidates.push(`${model.name} ${model.title}`);
  }
  if (model.name) {
    candidates.push(model.name);
  }
  return candidates;
}

function cleanInputLine(rawLine: string): string {
  const line = rawLine.trim();
  if (!line) {
    return "";
  }
  if (line.endsWith(":")) {
    return "";
  }
  if (line.includes("@") && line.endsWith(")")) {
    return "";
  }
  if (line.startsWith("(") && line.endsWith(")")) {
    return "";
  }
  return line.replace(/^[-*\u2022]+\s*/, "").trim();
}

function resolveEntry(rawName: string): CatalogEntry | undefined {
  const direct = catalog.get(normalize(rawName));
  if (direct) {
    return direct;
  }

  const withoutParentheticalMatch = rawName.match(/^(?<name>.+?)\s+\([^)]*\)$/);
  if (withoutParentheticalMatch?.groups?.name) {
    return resolveEntry(withoutParentheticalMatch.groups.name.trim());
  }

  const variantMatch = rawName.match(/^(?<name>.+?)\s+[A-Z]$/);
  if (variantMatch?.groups?.name) {
    return resolveEntry(variantMatch.groups.name.trim());
  }

  return undefined;
}

function normalize(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}
