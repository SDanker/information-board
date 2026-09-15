"use client";

import BrandMark from "@/components/BrandMark";
import LanguageSwitcher from "@/components/LanguageSwitcher";

/** Brand and language picker shown on pages visitors open without signing in. */
export default function PublicHeader() {
  return (
    <div className="public-header">
      <BrandMark variant="public" />
      <LanguageSwitcher />
    </div>
  );
}
