"use client";

import { Activity } from "lucide-react";

import { useBranding } from "@/lib/branding";

type BrandMarkProps = {
  variant: "sidebar" | "login" | "board" | "public";
  showOrganization?: boolean;
};

/** Logo (or a neutral icon when none was uploaded) plus the configured application name. */
export default function BrandMark({ variant, showOrganization = true }: BrandMarkProps) {
  const { branding } = useBranding();
  const name = branding?.app_name ?? "Information Board";
  const organization = showOrganization ? branding?.organization_name : "";

  return (
    <div className={`brand-block brand-block-${variant}`}>
      <span className={`brand-emblem ${branding?.logo_url ? "brand-emblem-logo" : ""}`}>
        {branding?.logo_url ? <img src={branding.logo_url} alt="" /> : <Activity aria-hidden />}
      </span>
      <span className="brand-text">
        <strong>{name}</strong>
        {organization && <small>{organization}</small>}
      </span>
    </div>
  );
}
