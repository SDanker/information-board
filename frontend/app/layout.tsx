import type { Metadata } from "next";
import { Inter, Manrope } from "next/font/google";

import Providers from "@/components/Providers";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const manrope = Manrope({ subsets: ["latin"], variable: "--font-manrope" });

// Generic metadata only: the configured name and logo are applied on the client by BrandingProvider.
export const metadata: Metadata = {
  title: "Information Board",
  description: "Digital signage for local networks",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} ${manrope.variable}`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
