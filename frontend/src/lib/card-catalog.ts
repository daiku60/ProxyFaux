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
  alternates?: string[];
  crewCard?: string;
  faction?: string;
  files?: CardFiles;
  keywords?: string[];
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
  includeUpgradesFromKeywords?: boolean;
};

export type PreviewCard = {
  frontPath: string;
  id: string;
  label: string;
};

export type CatalogSuggestion = {
  id: string;
  kind: "crewCard" | "model" | "upgrade";
  label: string;
};

type CatalogEntry = {
  aliases: string[];
  alternateIds: string[];
  crewCardId?: string;
  fronts: string[];
  id: string;
  kind: "crewCard" | "model" | "upgrade";
  keywords: string[];
  label: string;
  title?: string;
};

const rawCatalog = cardsData as RawCatalog;
const { entriesById, lookup, upgradeIdsByKeyword } = buildCatalog(rawCatalog);

const searchableEntries = Array.from(entriesById.values());

export function parseRosterPreview(
  text: string,
  options: ParseRosterPreviewOptions = {},
): PreviewCard[] {
  const { includeCrewCards = false, includeUpgradesFromKeywords = false } = options;
  const previews: PreviewCard[] = [];
  const autoCrewCardIds = new Set<string>();
  const counters = new Map<string, number>();
  const autoUpgradeIds = new Set<string>();
  const modelKeywordSet = new Set<string>();

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

    if (entry.kind === "model") {
      for (const keyword of entry.keywords) {
        modelKeywordSet.add(keyword);
      }
    } else if (entry.kind === "upgrade") {
      autoUpgradeIds.add(entry.id);
    }

    if (includeCrewCards && entry.kind === "model" && entry.crewCardId) {
      for (const crewCardEntry of collectCrewCardEntries(entry.crewCardId)) {
        if (autoCrewCardIds.has(crewCardEntry.id)) {
          continue;
        }
        previews.push(buildPreviewCard(crewCardEntry, counters));
        autoCrewCardIds.add(crewCardEntry.id);
      }
    }
  }

  if (includeUpgradesFromKeywords) {
    for (const keyword of modelKeywordSet) {
      const upgradeIds = upgradeIdsByKeyword.get(normalize(keyword)) ?? [];
      for (const upgradeId of upgradeIds) {
        if (autoUpgradeIds.has(upgradeId)) {
          continue;
        }
        const upgradeEntry = entriesById.get(upgradeId);
        if (!upgradeEntry || upgradeEntry.kind !== "upgrade" || upgradeEntry.fronts.length === 0) {
          continue;
        }
        previews.push(buildPreviewCard(upgradeEntry, counters));
        autoUpgradeIds.add(upgradeId);
      }
    }
  }

  return previews;
}

export function searchCatalog(query: string, limit = 8): CatalogSuggestion[] {
  const normalizedQuery = normalize(query);
  if (!normalizedQuery) {
    return [];
  }

  return searchableEntries
    .map((entry) => ({
      entry,
      score: scoreSuggestion(entry, normalizedQuery),
    }))
    .filter(({ score }) => score > 0)
    .sort((left, right) => {
      if (right.score !== left.score) {
        return right.score - left.score;
      }
      return left.entry.label.localeCompare(right.entry.label);
    })
    .slice(0, limit)
    .map(({ entry }) => ({
      id: entry.id,
      kind: entry.kind,
      label: entry.label,
    }));
}

function buildCatalog(rawCatalog: RawCatalog): {
  entriesById: Map<string, CatalogEntry>;
  lookup: Map<string, CatalogEntry>;
  upgradeIdsByKeyword: Map<string, string[]>;
} {
  const entriesById = new Map<string, CatalogEntry>();
  const lookup = new Map<string, CatalogEntry>();
  const upgradeIdsByKeyword = new Map<string, string[]>();

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
    if (entry.kind === "upgrade") {
      for (const keyword of entry.keywords) {
        const normalizedKeyword = normalize(keyword);
        if (!normalizedKeyword) {
          continue;
        }
        const existingUpgradeIds = upgradeIdsByKeyword.get(normalizedKeyword) ?? [];
        existingUpgradeIds.push(entry.id);
        upgradeIdsByKeyword.set(normalizedKeyword, existingUpgradeIds);
      }
    }
  }

  return { entriesById, lookup, upgradeIdsByKeyword };
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
    alternateIds: Array.isArray(model.alternates)
      ? model.alternates.filter(
          (alternateId): alternateId is string =>
            typeof alternateId === "string" && alternateId.trim().length > 0,
        )
      : [],
    crewCardId: model.crewCard,
    fronts,
    id,
    kind,
    keywords: Array.isArray(model.keywords)
      ? model.keywords.filter((keyword): keyword is string => typeof keyword === "string" && keyword.trim().length > 0)
      : [],
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

function collectCrewCardEntries(crewCardId: string): CatalogEntry[] {
  const seen = new Set<string>();
  const collected: CatalogEntry[] = [];
  const pendingIds = [crewCardId];

  while (pendingIds.length > 0) {
    const currentId = pendingIds.shift();
    if (!currentId || seen.has(currentId)) {
      continue;
    }
    seen.add(currentId);

    const entry = entriesById.get(currentId);
    if (!entry || entry.kind !== "crewCard" || entry.fronts.length === 0) {
      continue;
    }

    collected.push(entry);
    for (const alternateId of entry.alternateIds) {
      if (!seen.has(alternateId)) {
        pendingIds.push(alternateId);
      }
    }
  }

  return collected;
}

function scoreSuggestion(entry: CatalogEntry, normalizedQuery: string): number {
  let bestScore = 0;

  for (const alias of entry.aliases) {
    const normalizedAlias = normalize(alias);
    if (!normalizedAlias) {
      continue;
    }
    if (normalizedAlias === normalizedQuery) {
      bestScore = Math.max(bestScore, 500);
      continue;
    }
    if (normalizedAlias.startsWith(normalizedQuery)) {
      bestScore = Math.max(bestScore, 400 - normalizedAlias.length);
      continue;
    }
    if (normalizedAlias.includes(normalizedQuery)) {
      bestScore = Math.max(bestScore, 250 - normalizedAlias.length);
      continue;
    }
    if (normalizedQuery.split(" ").every((part) => normalizedAlias.includes(part))) {
      bestScore = Math.max(bestScore, 150 - normalizedAlias.length);
    }
  }

  return bestScore;
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
