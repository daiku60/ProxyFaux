import axios from "axios";
import type { CardLanguage } from "@/lib/card-catalog";

export type SelectedCardPayload = {
  kind: "crewCard" | "model" | "upgrade";
  label: string;
  language: CardLanguage;
  source_id: string;
  variant?: string | null;
};

export type CreatePdfPayload = {
  border: boolean;
  cut_lines: boolean;
  selected_cards?: SelectedCardPayload[];
  sheet_size: "a4" | "letter";
  text?: string;
};

export type CreatePdfResponse = {
  url: string;
};

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 5000,
});

export function buildCardImageUrl(relativePath: string): string {
  const encodedPath = relativePath
    .split("/")
    .map((part) => encodeURIComponent(part))
    .join("/");
  const apiBase = api.defaults.baseURL ?? "/api";
  const root = apiBase.toString().replace(/\/api\/?$/, "");
  return `${root}/api/card-images/${encodedPath}`;
}

export async function createPdf(payload: CreatePdfPayload): Promise<CreatePdfResponse> {
  const response = await api.post<CreatePdfResponse>("/create-pdf/", payload);
  return response.data;
}
