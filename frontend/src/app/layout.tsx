import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import "./globals.css";


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
      className={`${body.variable} ${mono.variable}`}
      lang="pt-BR"
      suppressHydrationWarning
    >
      <head>
        <meta name="darkreader-lock" />
      </head>
      <body>{children}</body>
    </html>
  );
}
