"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "overview" },
  { href: "/review", label: "review" },
  { href: "/templates", label: "templates" },
  { href: "/models", label: "models" },
];

export default function Nav() {
  const path = usePathname();
  return (
    <nav>
      {LINKS.map((l) => (
        <Link key={l.href} href={l.href} className={path === l.href ? "on" : ""}>{l.label}</Link>
      ))}
    </nav>
  );
}
