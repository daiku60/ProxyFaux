import { useDeferredValue, useMemo, useState } from "react";
import { LoaderCircle, Sparkles } from "lucide-react";

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
import { parseRosterPreview, type SheetSize } from "@/lib/card-catalog";

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
  const [rosterText, setRosterText] = useState(SAMPLE_TEXT);
  const [sheetSize, setSheetSize] = useState<SheetSize>("a4");
  const [border, setBorder] = useState(false);
  const [cutLines, setCutLines] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [isExporting, setIsExporting] = useState(false);

  const deferredRosterText = useDeferredValue(rosterText);
  const previewCards = useMemo(
    () => parseRosterPreview(deferredRosterText),
    [deferredRosterText],
  );

  async function handleExport() {
    setIsExporting(true);
    setErrorMessage("");

    try {
      const response = await createPdf({
        border,
        cut_lines: cutLines,
        sheet_size: sheetSize,
        text: rosterText,
      });
      window.open(response.url, "_blank", "noopener,noreferrer");
    } catch (error) {
      setErrorMessage("The export could not be created. Check the roster text and try again.");
      console.error(error);
    } finally {
      setIsExporting(false);
    }
  }

  return (
    <section className="mx-auto max-w-7xl px-6 py-10 md:py-14">
      <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <Card className="overflow-hidden bg-[linear-gradient(180deg,rgba(255,255,255,0.92),rgba(247,236,224,0.92))]">
          <CardHeader className="border-b border-border/60 bg-[radial-gradient(circle_at_top_left,rgba(206,111,87,0.18),transparent_42%)]">
            <div className="flex items-center gap-3 text-primary">
              <Sparkles className="h-5 w-5" />
              <span className="text-xs font-semibold uppercase tracking-[0.28em]">
                Main Sheet
              </span>
            </div>
            <CardTitle>Paste a crew list and export printable proxies</CardTitle>
            <CardDescription>
              The text parser matches model names and titles, previews the front cards,
              and sends the selected export options to the PDF API.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6 p-6">
            <div className="space-y-3">
              <Label htmlFor="roster-text">Roster text</Label>
              <Textarea
                id="roster-text"
                value={rosterText}
                onChange={(event) => setRosterText(event.target.value)}
                className="min-h-[360px] resize-y bg-background/90"
              />
            </div>

            <div className="grid gap-4 md:grid-cols-3">
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
                disabled={isExporting || !rosterText.trim()}
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
                The generated PDF opens in a new tab once the API returns its URL.
              </p>
            </div>
          </CardContent>
        </Card>

        <Card className="overflow-hidden bg-[linear-gradient(180deg,rgba(247,240,234,0.94),rgba(255,255,255,0.92))]">
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
              <div className="grid gap-4 sm:grid-cols-2">
                {previewCards.map((previewCard) => (
                  <figure
                    key={previewCard.id}
                    className="preview-card overflow-hidden rounded-[1.4rem] border border-border bg-card shadow-card"
                  >
                    <div className="aspect-[5/7] bg-muted">
                      <img
                        src={buildCardImageUrl(previewCard.frontPath)}
                        alt={previewCard.label}
                        className="h-full w-full object-cover"
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
            )}
          </CardContent>
        </Card>
      </div>
    </section>
  );
}

type OptionToggleProps = {
  checked: boolean;
  description: string;
  id: string;
  label: string;
  onCheckedChange: (checked: boolean) => void;
};

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
