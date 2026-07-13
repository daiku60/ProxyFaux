import { useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import { Check, ChevronsUpDown, LoaderCircle, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { createPdf, buildCardImageUrl } from "@/lib/api";
import {
  type CardLanguage,
  parseRosterPreview,
  searchCatalog,
  type CatalogSuggestion,
  type SheetSize,
} from "@/lib/card-catalog";

const SAMPLE_TEXT = `Brew @ Informants (Bayou)
Leader:
  Brewmaster, Proof Prophet
Totem(s):
  Apprentice Wesley
Hires:
  Hopscotch
  Shojo
  Popcorn Turner
  Barrelby
  Squish and Squash
  Lucky Fate, Effigy
  Nia, Life of the Party
References:
  Whiskey Gamin
  Lucky Fate, Emissary`;

export default function Home() {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [rosterText, setRosterText] = useState("");
  const [sheetSize, setSheetSize] = useState<SheetSize>("a4");
  const [border, setBorder] = useState(false);
  const [cutLines, setCutLines] = useState(false);
  const [includeCrewCards, setIncludeCrewCards] = useState(false);
  const [includeUpgradesFromKeywords, setIncludeUpgradesFromKeywords] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [isExporting, setIsExporting] = useState(false);
  const [selectedPreviewIds, setSelectedPreviewIds] = useState<Record<string, boolean>>({});
  const [selectedPreviewLanguages, setSelectedPreviewLanguages] = useState<Record<string, CardLanguage>>({});
  const [suggestions, setSuggestions] = useState<CatalogSuggestion[]>([]);
  const [highlightedSuggestionIndex, setHighlightedSuggestionIndex] = useState(0);
  const [suggestionPosition, setSuggestionPosition] = useState({ left: 20, top: 20 });
  const [suggestionsDismissed, setSuggestionsDismissed] = useState(false);

  const deferredRosterText = useDeferredValue(rosterText);
  const previewCards = useMemo(
    () =>
      parseRosterPreview(deferredRosterText, {
        includeCrewCards,
        includeUpgradesFromKeywords,
      }),
    [deferredRosterText, includeCrewCards, includeUpgradesFromKeywords],
  );
  const selectedPreviewCards = useMemo(
    () => previewCards.filter((previewCard) => selectedPreviewIds[previewCard.id] !== false),
    [previewCards, selectedPreviewIds],
  );

  useEffect(() => {
    setSelectedPreviewIds((currentSelection) => {
      const nextSelection: Record<string, boolean> = {};
      for (const previewCard of previewCards) {
        nextSelection[previewCard.id] = currentSelection[previewCard.id] ?? true;
      }
      return nextSelection;
    });
  }, [previewCards]);

  useEffect(() => {
    setSelectedPreviewLanguages((currentLanguages) => {
      const nextLanguages: Record<string, CardLanguage> = {};
      for (const previewCard of previewCards) {
        const currentLanguage = currentLanguages[previewCard.id];
        nextLanguages[previewCard.id] = previewCard.languageOptions.includes(currentLanguage as CardLanguage)
          ? (currentLanguage as CardLanguage)
          : "en";
      }
      return nextLanguages;
    });
  }, [previewCards]);

  useEffect(() => {
    if (highlightedSuggestionIndex >= suggestions.length) {
      setHighlightedSuggestionIndex(0);
    }
  }, [highlightedSuggestionIndex, suggestions.length]);

  async function handleExport() {
    const exportText = selectedPreviewCards.map((previewCard) => previewCard.label).join("\n");
    const previewWindow = window.open("", "_blank");
    if (previewWindow) {
      previewWindow.document.write(
        "<!doctype html><title>Preparing PDF...</title><body style=\"font-family: sans-serif; padding: 24px;\">Preparing PDF...</body>",
      );
      previewWindow.document.close();
    }

    setIsExporting(true);
    setErrorMessage("");

    try {
      const response = await createPdf({
        border,
        cut_lines: cutLines,
        selected_cards: selectedPreviewCards.map((previewCard) => ({
          kind: previewCard.kind,
          label: previewCard.label,
          language: selectedPreviewLanguages[previewCard.id] ?? "en",
          source_id: previewCard.sourceId,
          variant: previewCard.variant,
        })),
        sheet_size: sheetSize,
        text: exportText,
      });
      if (previewWindow && !previewWindow.closed) {
        previewWindow.location.href = response.url;
      } else {
        window.location.href = response.url;
      }
    } catch (error) {
      if (previewWindow && !previewWindow.closed) {
        previewWindow.close();
      }
      setErrorMessage("The export could not be created. Check the roster text and try again.");
      console.error(error);
    } finally {
      setIsExporting(false);
    }
  }

  function togglePreviewSelection(previewId: string) {
    setSelectedPreviewIds((currentSelection) => ({
      ...currentSelection,
      [previewId]: currentSelection[previewId] === false,
    }));
  }

  function updatePreviewLanguage(previewId: string, language: CardLanguage) {
    setSelectedPreviewLanguages((currentLanguages) => ({
      ...currentLanguages,
      [previewId]: language,
    }));
  }

  function updateSuggestions(
    value: string,
    selectionStart: number,
    textarea: HTMLTextAreaElement | null,
  ) {
    if (suggestionsDismissed) {
      setSuggestions([]);
      return;
    }

    const lineInfo = getCurrentLineInfo(value, selectionStart);
    if (!lineInfo) {
      setSuggestions([]);
      return;
    }

    const nextSuggestions = searchCatalog(lineInfo.query);
    setSuggestions(nextSuggestions);
    setHighlightedSuggestionIndex(0);

    if (textarea && nextSuggestions.length > 0) {
      setSuggestionPosition(getSuggestionPosition(textarea, selectionStart));
    }
  }

  function applySuggestion(suggestion: CatalogSuggestion) {
    const textarea = textareaRef.current;
    const selectionStart = textarea?.selectionStart ?? rosterText.length;
    const lineInfo = getCurrentLineInfo(rosterText, selectionStart);
    if (!lineInfo) {
      return;
    }

    const nextValue =
      rosterText.slice(0, lineInfo.lineStart) +
      `${lineInfo.prefix}${suggestion.label}` +
      rosterText.slice(lineInfo.lineEnd);
    const nextCaretPosition = lineInfo.lineStart + lineInfo.prefix.length + suggestion.label.length;

    setRosterText(nextValue);
    setSuggestions([]);
    setSuggestionsDismissed(false);

    window.requestAnimationFrame(() => {
      if (!textareaRef.current) {
        return;
      }
      textareaRef.current.focus();
      textareaRef.current.setSelectionRange(nextCaretPosition, nextCaretPosition);
    });
  }

  return (
    <section className="mx-auto max-w-7xl px-6 py-10 md:py-14">
      <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <Card className="overflow-hidden">
          <CardHeader>
            <CardTitle>Paste a crew list and export printable proxies</CardTitle>
            <CardDescription>
              The text parser matches model names and titles, previews the front cards,
              and sends only the checked cards with the selected export options to the PDF API.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6 p-6">
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <Label htmlFor="roster-text">Roster text</Label>
                {rosterText ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setRosterText("")}
                    aria-label="Clear roster text"
                  >
                    <X className="h-4 w-4" />
                    Clear
                  </Button>
                ) : null}
              </div>
              <div className="relative">
                <Textarea
                  id="roster-text"
                  ref={textareaRef}
                  placeholder={SAMPLE_TEXT}
                  value={rosterText}
                  onChange={(event) => {
                    setSuggestionsDismissed(false);
                    setRosterText(event.target.value);
                    updateSuggestions(
                      event.target.value,
                      event.target.selectionStart,
                      event.target,
                    );
                  }}
                  onClick={(event) =>
                    updateSuggestions(
                      event.currentTarget.value,
                      event.currentTarget.selectionStart,
                      event.currentTarget,
                    )
                  }
                  onKeyUp={(event) => {
                    if (["ArrowDown", "ArrowUp", "Enter", "Tab", "Escape"].includes(event.key)) {
                      return;
                    }
                    updateSuggestions(
                      event.currentTarget.value,
                      event.currentTarget.selectionStart,
                      event.currentTarget,
                    );
                  }}
                  onBlur={() => {
                    window.setTimeout(() => setSuggestions([]), 120);
                  }}
                  onKeyDown={(event) => {
                    if (suggestions.length === 0) {
                      return;
                    }
                    if (event.key === "ArrowDown") {
                      event.preventDefault();
                      setHighlightedSuggestionIndex((currentIndex) =>
                        (currentIndex + 1) % suggestions.length,
                      );
                    } else if (event.key === "ArrowUp") {
                      event.preventDefault();
                      setHighlightedSuggestionIndex((currentIndex) =>
                        (currentIndex - 1 + suggestions.length) % suggestions.length,
                      );
                    } else if (event.key === "Enter" || event.key === "Tab") {
                      event.preventDefault();
                      const suggestion = suggestions[highlightedSuggestionIndex];
                      if (suggestion) {
                        applySuggestion(suggestion);
                      }
                    } else if (event.key === "Escape") {
                      setSuggestionsDismissed(true);
                      setSuggestions([]);
                    }
                  }}
                  className="min-h-[360px] resize-y bg-background/90"
                />
                {suggestions.length > 0 ? (
                  <div
                    className="absolute z-20 w-[min(24rem,calc(100%-1rem))] overflow-hidden rounded-[1.2rem] border border-border bg-popover shadow-card"
                    style={{
                      left: Math.max(8, suggestionPosition.left),
                      top: suggestionPosition.top,
                    }}
                  >
                    <div className="border-b border-border/70 px-3 py-2 text-xs uppercase tracking-[0.22em] text-muted-foreground">
                      Suggestions
                    </div>
                    <div className="max-h-72 overflow-y-auto py-1">
                      {suggestions.map((suggestion, index) => (
                        <button
                          key={`${suggestion.kind}-${suggestion.id}`}
                          type="button"
                          onMouseDown={(event) => {
                            event.preventDefault();
                            applySuggestion(suggestion);
                          }}
                          className={
                            index === highlightedSuggestionIndex
                              ? "flex w-full items-center justify-between gap-3 bg-secondary px-3 py-2 text-left text-sm text-secondary-foreground"
                              : "flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm transition hover:bg-secondary hover:text-secondary-foreground"
                          }
                        >
                          <span className="truncate">{suggestion.label}</span>
                          <span className="rounded-full border border-border/80 px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                            {suggestion.kind}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}
                <div className="pointer-events-none absolute bottom-4 right-4 text-muted-foreground/60">
                  <ChevronsUpDown className="h-4 w-4" />
                </div>
              </div>
            </div>

            <div className="xl:hidden">
              <PreviewPanel
                previewCards={previewCards}
                selectedPreviewCards={selectedPreviewCards}
                selectedPreviewIds={selectedPreviewIds}
                selectedPreviewLanguages={selectedPreviewLanguages}
                setSelectedPreviewIds={setSelectedPreviewIds}
                togglePreviewSelection={togglePreviewSelection}
                updatePreviewLanguage={updatePreviewLanguage}
              />
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <OptionSection
                title="Layout"
                description="Configure the sheet format and printed cut guides."
              >
                <div className="space-y-3">
                  <Label htmlFor="sheet-size">Sheet size</Label>
                  <Select value={sheetSize} onValueChange={(value) => setSheetSize(value as SheetSize)}>
                    <SelectTrigger id="sheet-size">
                      <SelectValue placeholder="Select a sheet size" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="letter">Letter</SelectItem>
                      <SelectItem value="a4">A4</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <OptionToggle
                  checked={border}
                  description="Draw one outer border around each front/back pair."
                  id="include-border"
                  label="Include border"
                  onCheckedChange={setBorder}
                />

                <OptionToggle
                  checked={cutLines}
                  description="Extend cut guides from the card edges to the sheet border."
                  id="include-cut-lines"
                  label="Include cut lines"
                  onCheckedChange={setCutLines}
                />
              </OptionSection>

              <OptionSection
                title="Options"
                description="Expand the card list with related crew cards and upgrades."
              >
                <OptionToggle
                  checked={includeCrewCards}
                  description="Automatically add linked crew cards when matched models have one."
                  id="include-crew-cards"
                  label="Include crew cards"
                  onCheckedChange={setIncludeCrewCards}
                />

                <OptionToggle
                  checked={includeUpgradesFromKeywords}
                  description="Automatically add upgrades tied to the keywords of included models."
                  id="include-upgrades-from-keywords"
                  label="Include upgrades from keywords"
                  onCheckedChange={setIncludeUpgradesFromKeywords}
                />
              </OptionSection>
            </div>

            {errorMessage ? (
              <div className="rounded-[1.2rem] border border-destructive/25 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                {errorMessage}
              </div>
            ) : null}

            <div className="flex flex-wrap items-center gap-3">
              <Button
                size="lg"
                onClick={() => void handleExport()}
                disabled={isExporting || selectedPreviewCards.length === 0}
              >
                {isExporting ? (
                  <>
                    <LoaderCircle className="mr-2 h-4 w-4 animate-spin" />
                    Creating PDF
                  </>
                ) : (
                  "Create export"
                )}
              </Button>
              <p className="text-sm text-muted-foreground">
                The generated PDF includes only the checked preview cards and opens in a new tab.
              </p>
            </div>
          </CardContent>
        </Card>

        <div className="hidden xl:block">
          <PreviewPanel
            previewCards={previewCards}
            selectedPreviewCards={selectedPreviewCards}
            selectedPreviewIds={selectedPreviewIds}
            selectedPreviewLanguages={selectedPreviewLanguages}
            setSelectedPreviewIds={setSelectedPreviewIds}
            togglePreviewSelection={togglePreviewSelection}
            updatePreviewLanguage={updatePreviewLanguage}
          />
        </div>
      </div>
    </section>
  );
}

type PreviewPanelProps = {
  previewCards: ReturnType<typeof parseRosterPreview>;
  selectedPreviewCards: ReturnType<typeof parseRosterPreview>;
  selectedPreviewIds: Record<string, boolean>;
  selectedPreviewLanguages: Record<string, CardLanguage>;
  setSelectedPreviewIds: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
  togglePreviewSelection: (previewId: string) => void;
  updatePreviewLanguage: (previewId: string, language: CardLanguage) => void;
};

function PreviewPanel({
  previewCards,
  selectedPreviewCards,
  selectedPreviewIds,
  selectedPreviewLanguages,
  setSelectedPreviewIds,
  togglePreviewSelection,
  updatePreviewLanguage,
}: PreviewPanelProps) {
  return (
    <Card className="overflow-hidden bg-[image:var(--panel-gradient)]">
      <CardHeader className="border-b border-border/60">
        <CardTitle>Front-side preview</CardTitle>
        <CardDescription>
          Previewed from the local card catalog before export. Repeated models advance
          through alternate fronts when available.
        </CardDescription>
      </CardHeader>
      <CardContent className="p-6">
        {previewCards.length === 0 ? (
          <div className="flex min-h-[420px] items-center justify-center rounded-[1.5rem] border border-dashed border-border bg-background/50 px-8 text-center text-sm text-muted-foreground">
            Paste a roster on the left to see matching front-card previews here.
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-between gap-3 rounded-[1.25rem] border border-border/70 bg-background/55 px-4 py-3 text-sm text-muted-foreground">
              <span>{selectedPreviewCards.length} of {previewCards.length} selected</span>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() =>
                  setSelectedPreviewIds(
                    Object.fromEntries(previewCards.map((previewCard) => [previewCard.id, true])),
                  )
                }
                disabled={selectedPreviewCards.length === previewCards.length}
              >
                Select all
              </Button>
            </div>
            <div className="-mx-1 flex snap-x snap-mandatory gap-4 overflow-x-auto px-1 pb-2 xl:mx-0 xl:grid xl:gap-4 xl:overflow-visible xl:px-0 xl:pb-0 xl:sm:grid-cols-2">
              {previewCards.map((previewCard) => (
                <figure
                  key={previewCard.id}
                  className="preview-card group relative min-w-[15.5rem] shrink-0 snap-start overflow-hidden rounded-[1.4rem] border border-border bg-card shadow-card xl:min-w-0"
                >
                  <div className="absolute right-3 top-3 z-10 flex items-center gap-2">
                    <Select
                      value={selectedPreviewLanguages[previewCard.id] ?? "en"}
                      onValueChange={(value) => updatePreviewLanguage(previewCard.id, value as CardLanguage)}
                    >
                      <SelectTrigger className="h-8 w-[4.5rem] rounded-full border-white/60 bg-background/88 px-2 text-xs shadow-lg backdrop-blur">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="en">🇬🇧 EN</SelectItem>
                        {previewCard.languageOptions.includes("es") ? (
                          <SelectItem value="es">🇪🇸 ES</SelectItem>
                        ) : null}
                      </SelectContent>
                    </Select>
                    <button
                      type="button"
                      onClick={() => togglePreviewSelection(previewCard.id)}
                      aria-label={
                        selectedPreviewIds[previewCard.id] === false
                          ? `Select ${previewCard.label}`
                          : `Deselect ${previewCard.label}`
                      }
                      aria-pressed={selectedPreviewIds[previewCard.id] !== false}
                      className="flex h-8 w-8 items-center justify-center rounded-full border border-white/60 bg-background/88 text-foreground shadow-lg backdrop-blur transition hover:scale-105 hover:bg-background"
                    >
                      {selectedPreviewIds[previewCard.id] !== false ? (
                        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-primary-foreground">
                          <Check className="h-3.5 w-3.5" />
                        </span>
                      ) : (
                        <span className="h-5 w-5 rounded-full border border-border/80 bg-card" />
                      )}
                    </button>
                  </div>
                  <div className="aspect-[5/7] bg-muted">
                    <img
                      src={buildCardImageUrl(previewCard.frontPath)}
                      alt={previewCard.label}
                      className={
                        selectedPreviewIds[previewCard.id] === false
                          ? "h-full w-full object-cover opacity-45 grayscale transition"
                          : "h-full w-full object-cover transition"
                      }
                      decoding="async"
                      loading="lazy"
                    />
                  </div>
                  <figcaption className="border-t border-border/70 px-4 py-3 text-sm font-medium">
                    {previewCard.label}
                  </figcaption>
                </figure>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

type OptionToggleProps = {
  checked: boolean;
  description: string;
  id: string;
  label: string;
  onCheckedChange: (checked: boolean) => void;
};

type OptionSectionProps = {
  children: React.ReactNode;
  description: string;
  title: string;
};

function OptionSection({ children, description, title }: OptionSectionProps) {
  return (
    <section className="space-y-4 rounded-[1.4rem] border border-border/70 bg-background/55 p-4">
      <div className="space-y-1.5">
        <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-primary/80">
          {title}
        </h3>
        <p className="text-sm leading-5 text-muted-foreground">{description}</p>
      </div>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function OptionToggle({
  checked,
  description,
  id,
  label,
  onCheckedChange,
}: OptionToggleProps) {
  return (
    <div className="rounded-[1.25rem] border border-border bg-background/75 p-4">
      <div className="flex items-start gap-3">
        <Checkbox
          id={id}
          checked={checked}
          onCheckedChange={(value) => onCheckedChange(value === true)}
          className="mt-0.5"
        />
        <div className="space-y-1.5">
          <Label htmlFor={id}>{label}</Label>
          <p className="text-sm leading-5 text-muted-foreground">{description}</p>
        </div>
      </div>
    </div>
  );
}

type LineInfo = {
  lineEnd: number;
  lineStart: number;
  prefix: string;
  query: string;
};

function getCurrentLineInfo(value: string, selectionStart: number): LineInfo | null {
  const lineStart = value.lastIndexOf("\n", Math.max(selectionStart - 1, 0)) + 1;
  const rawLineEnd = value.indexOf("\n", selectionStart);
  const lineEnd = rawLineEnd === -1 ? value.length : rawLineEnd;
  const line = value.slice(lineStart, lineEnd);
  const prefixMatch = line.match(/^(\s*[-*\u2022]?\s*)/);
  const prefix = prefixMatch?.[1] ?? "";
  const query = line.slice(prefix.length).trim();

  if (!query || query.endsWith(":")) {
    return null;
  }
  if (query.includes("@") && query.endsWith(")")) {
    return null;
  }
  if (query.startsWith("(") && query.endsWith(")")) {
    return null;
  }

  return {
    lineEnd,
    lineStart,
    prefix,
    query,
  };
}

function getSuggestionPosition(
  textarea: HTMLTextAreaElement,
  selectionStart: number,
): { left: number; top: number } {
  const computed = window.getComputedStyle(textarea);
  const mirror = document.createElement("div");
  const marker = document.createElement("span");

  mirror.style.position = "absolute";
  mirror.style.visibility = "hidden";
  mirror.style.whiteSpace = "pre-wrap";
  mirror.style.wordWrap = "break-word";
  mirror.style.overflow = "hidden";
  mirror.style.top = "0";
  mirror.style.left = "0";
  mirror.style.width = `${textarea.clientWidth}px`;

  const mirroredStyles = [
    "borderTopWidth",
    "borderRightWidth",
    "borderBottomWidth",
    "borderLeftWidth",
    "boxSizing",
    "fontFamily",
    "fontSize",
    "fontStyle",
    "fontWeight",
    "letterSpacing",
    "lineHeight",
    "paddingTop",
    "paddingRight",
    "paddingBottom",
    "paddingLeft",
    "textIndent",
    "textTransform",
  ] as const;

  for (const styleName of mirroredStyles) {
    mirror.style[styleName] = computed[styleName];
  }

  mirror.textContent = textarea.value.slice(0, selectionStart);
  marker.textContent = "\u200b";
  mirror.appendChild(marker);
  document.body.appendChild(mirror);

  const left = marker.offsetLeft - textarea.scrollLeft + 12;
  const top = marker.offsetTop - textarea.scrollTop + getLineHeight(computed.lineHeight, computed.fontSize) + 12;

  document.body.removeChild(mirror);

  return {
    left,
    top,
  };
}

function getLineHeight(lineHeight: string, fontSize: string): number {
  if (lineHeight.endsWith("px")) {
    return Number.parseFloat(lineHeight);
  }
  if (fontSize.endsWith("px")) {
    return Number.parseFloat(fontSize) * 1.4;
  }
  return 22;
}
