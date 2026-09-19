export const API = process.env.NEXT_PUBLIC_API_URL ?? "";

export async function api<T>(path: string, init?: RequestInit, timeoutMs = 15000): Promise<T> {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), timeoutMs);
  let r: Response;
  try {
    r = await fetch(`${API}${path}`, { ...init, signal: ctl.signal });
  } catch (e) {
    throw new Error(`API unreachable (${API || "same origin"}${path}): ${e}`);
  } finally {
    clearTimeout(t);
  }
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
