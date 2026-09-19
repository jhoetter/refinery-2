"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "overview" },
  { href: "/browse", label: "browse" },
  { href: "/label", label: "label" },
  { href: "/templates", label: "templates" },
  { href: "/models", label: "models" },
];

export default function Nav() {
  const path = usePathname();
  const active = path === "/" ? "/" : "/" + path.split("/")[1];
  return (
    <nav>
      {LINKS.map((l) => (
        <Link key={l.href} href={l.href} className={active === l.href ? "on" : ""}>{l.label}</Link>
      ))}
    </nav>
  );
}
