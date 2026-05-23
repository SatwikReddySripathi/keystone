import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { ClientShell } from "@/components/ClientShell";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  title: "Keystone — Transaction Governance",
  description: "Govern every AI agent action before it reaches production.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.className} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{
          __html: `(function(){try{var t=localStorage.getItem('ks-theme');var d=t?t==='dark':window.matchMedia('(prefers-color-scheme: dark)').matches;if(d)document.documentElement.classList.add('dark');}catch(e){}})();`
        }} />
      </head>
      <body className="min-h-screen bg-ks-bg text-ks-text bg-grid-pattern flex overflow-hidden">
        <ClientShell>{children}</ClientShell>
      </body>
    </html>
  );
}
