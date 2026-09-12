import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, Oxanium } from "next/font/google";
import "./globals.css";

const display = Oxanium({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
});

const body = IBM_Plex_Sans({
  variable: "--font-body",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const mono = IBM_Plex_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "EnterOS · Inteligência para decisões jurídicas",
  description:
    "Workspace auditável para análise documental, risco judicial e política de acordos.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      className={`${display.variable} ${body.variable} ${mono.variable}`}
      lang="pt-BR"
    >
      <body>{children}</body>
    </html>
  );
}
