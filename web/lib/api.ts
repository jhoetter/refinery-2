export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API}${path}`, init);
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<T>;
}

export type TaskDef = {
  name: string;
  type: "classification" | "spans" | "extraction";
  description?: string;
  labels?: string[];
  entities?: string[];
  fields?: { name: string; prompt: string }[];
};

export function shortLabel(l: unknown): string {
  if (l == null) return "–";
  if (typeof l === "string") return l;
  if (Array.isArray(l)) return `${l.length} spans`;
  const o = l as Record<string, unknown>;
  return Object.keys(o).slice(0, 2).map((k) => `${k}=${String(o[k]).slice(0, 24)}`).join(" ");
}
