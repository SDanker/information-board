"use client";

import { BrandingProvider } from "@/lib/branding";
import { I18nProvider } from "@/lib/i18n";

/** Client-side context shared by every page: branding first, because the default language depends on it. */
export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <BrandingProvider>
      <I18nProvider>{children}</I18nProvider>
    </BrandingProvider>
  );
}
