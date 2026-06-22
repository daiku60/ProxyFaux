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
  crewCard?: string;
  faction?: string;
  files?: CardFiles;
  name?: string;
  title?: string;
};

type RawCatalog = {
  crewCards?: Record<string, RawCatalogModel>;
  models?: Record<string, RawCatalogModel>;
  upgrades?: Record<string, RawCatalogModel>;
};

type ParseRosterPreviewOptions = {
  includeCrewCards?: boolean;
};

export type PreviewCard = {
  frontPath: string;
  id: string;
  label: string;
};

type CatalogEntry = {
  aliases: string[];
  crewCardId?: string;
  fronts: string[];
  id: string;
  kind: "crewCard" | "model" | "upgrade";
  label: string;
  title?: string;
};

const rawCatalog = cardsData as RawCatalog;
const { entriesById, lookup } = buildCatalog(rawCatalog);

export function parseRosterPreview(
  text: string,
  options: ParseRosterPreviewOptions = {},
): PreviewCard[] {
  const { includeCrewCards = false } = options;
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

    previews.push(buildPreviewCard(entry, counters));

    if (includeCrewCards && entry.kind === "model" && entry.crewCardId) {
      const crewCardEntry = entriesById.get(entry.crewCardId);
      if (crewCardEntry && crewCardEntry.fronts.length > 0) {
        previews.push(buildPreviewCard(crewCardEntry, counters));
      }
    }
  }

  return previews;
}

function buildCatalog(rawCatalog: RawCatalog): {
  entriesById: Map<string, CatalogEntry>;
  lookup: Map<string, CatalogEntry>;
} {
  const entriesById = new Map<string, CatalogEntry>();
  const lookup = new Map<string, CatalogEntry>();

  for (const [id, model] of Object.entries(rawCatalog.models ?? {})) {
    const entry = buildCatalogEntry(id, model, "model");
    if (!entry) {
      continue;
    }
    entriesById.set(id, entry);
  }

  for (const [id, crewCard] of Object.entries(rawCatalog.crewCards ?? {})) {
    const entry = buildCatalogEntry(id, crewCard, "crewCard");
    if (!entry) {
      continue;
    }
    entriesById.set(id, entry);
  }

  for (const [id, upgrade] of Object.entries(rawCatalog.upgrades ?? {})) {
    const entry = buildCatalogEntry(id, upgrade, "upgrade");
    if (!entry) {
      continue;
    }
    entriesById.set(id, entry);
  }

  for (const entry of entriesById.values()) {
    for (const candidate of buildCandidates(entry)) {
      const normalized = normalize(candidate);
      if (normalized && !lookup.has(normalized)) {
        lookup.set(normalized, entry);
      }
    }
  }

  return { entriesById, lookup };
}

function buildCatalogEntry(
  id: string,
  model: RawCatalogModel,
  kind: "crewCard" | "model" | "upgrade",
): CatalogEntry | undefined {
  const fronts = (model.files?.versions ?? [])
    .map((version) => version.front)
    .filter((frontPath): frontPath is string => typeof frontPath === "string" && frontPath.length > 0);
  if (fronts.length === 0 || !model.name) {
    return undefined;
  }

  return {
    aliases: buildAliases(model),
    crewCardId: model.crewCard,
    fronts,
    id,
    kind,
    label: model.title ? `${model.name}, ${model.title}` : model.name,
    title: model.title,
  };
}

function buildCandidates(entry: CatalogEntry): string[] {
  return entry.aliases;
}

function buildPreviewCard(entry: CatalogEntry, counters: Map<string, number>): PreviewCard {
  const currentIndex = counters.get(entry.id) ?? 0;
  const frontPath = entry.fronts[Math.min(currentIndex, entry.fronts.length - 1)];
  counters.set(entry.id, currentIndex + 1);

  return {
    frontPath,
    id: `${entry.id}-${currentIndex}`,
    label: entry.label,
  };
}

function buildAliases(model: RawCatalogModel): string[] {
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
  const direct = lookup.get(normalize(rawName));
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
