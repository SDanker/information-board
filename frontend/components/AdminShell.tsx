"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Archive, CalendarClock, ChevronRight, FileText, LayoutDashboard,
  LogOut, Menu, Monitor, PlaySquare, Settings, ShieldCheck, Users, X,
} from "lucide-react";

import BrandMark from "@/components/BrandMark";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import { clearSession, useAuthReady } from "@/lib/auth";
import { PageKey, useBranding } from "@/lib/branding";
import { STORAGE_KEYS } from "@/lib/constants";
import { MessageKey, useI18n, usePageLabel } from "@/lib/i18n";

const NAVIGATION: { page: PageKey; href: string; icon: typeof LayoutDashboard; external?: boolean }[] = [
  { page: "dashboard", href: "/admin", icon: LayoutDashboard },
  { page: "screens", href: "/admin/screens", icon: Monitor },
  { page: "content", href: "/admin/content", icon: FileText },
  { page: "playlists", href: "/admin/playlists", icon: PlaySquare },
  { page: "library", href: "/library", icon: Archive, external: true },
  { page: "schedule", href: "/admin/schedule", icon: CalendarClock },
  { page: "users", href: "/admin/users", icon: Users },
  { page: "audit", href: "/admin/audit", icon: ShieldCheck },
  { page: "settings", href: "/admin/settings", icon: Settings },
];

type AdminShellProps = {
  children: React.ReactNode;
  page: PageKey;
  eyebrow: string;
};

export default function AdminShell({ children, page, eyebrow }: AdminShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const ready = useAuthReady();
  const { branding } = useBranding();
  const { t } = useI18n();
  const pageLabel = usePageLabel();
  const [open, setOpen] = useState(false);
  const [account, setAccount] = useState<{ username: string; role: string }>({ username: "", role: "" });

  useEffect(() => {
    setAccount({ username: localStorage.getItem(STORAGE_KEYS.user) ?? "", role: localStorage.getItem(STORAGE_KEYS.role) ?? "" });
  }, []);

  function logout() {
    clearSession();
    router.push("/login");
  }

  if (!ready) return <div className="loading-page"><span className="spinner" /> {t("common.checkingSession")}</div>;

  const navigation = NAVIGATION.filter((item) => item.page !== "library" || branding?.public_library_enabled !== false);
  const initials = account.username.slice(0, 2).toUpperCase() || "—";

  return (
    <div className="admin-app">
      <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
        <div className="brand">
          <BrandMark variant="sidebar" />
          <button className="sidebar-close" onClick={() => setOpen(false)} aria-label={t("common.closeMenu")}><X /></button>
        </div>
        <nav>
          <p className="nav-label">{t("nav.section")}</p>
          {navigation.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href;
            return (
              <Link
                key={item.page}
                href={item.href}
                target={item.external ? "_blank" : undefined}
                className={`nav-item ${active ? "active" : ""}`}
                onClick={() => {
                  if (!item.external) setOpen(false);
                }}
              >
                <Icon size={19} /><span>{pageLabel(item.page)}</span>{active && <ChevronRight size={16} />}
              </Link>
            );
          })}
        </nav>
        <div className="sidebar-language"><LanguageSwitcher tone="dark" /></div>
        <div className="sidebar-footer">
          <div className="user-badge">{initials}</div>
          <div>
            <strong>{account.username || "—"}</strong>
            <span>{account.role ? t(`role.${account.role}` as MessageKey) : ""}</span>
          </div>
          <button onClick={logout} aria-label={t("common.signOut")} title={t("common.signOut")}><LogOut size={18} /></button>
        </div>
      </aside>
      {open && <button className="sidebar-scrim" onClick={() => setOpen(false)} aria-label={t("common.closeMenu")} />}
      <main className="admin-main">
        <header className="topbar">
          <button className="menu-button" onClick={() => setOpen(true)} aria-label={t("common.openMenu")}><Menu /></button>
          <div><span>{eyebrow}</span><h1>{pageLabel(page)}</h1></div>
          <div className="system-pill"><i /> {t("common.systemOperational")}</div>
        </header>
        <div className="admin-content">{children}</div>
      </main>
    </div>
  );
}
