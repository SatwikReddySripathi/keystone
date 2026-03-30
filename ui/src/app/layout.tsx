import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { ThemeToggle } from "@/lib/ThemeToggle";
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
      <body className="min-h-screen bg-ks-bg text-ks-text">
        <header className="bg-ks-surface border-b border-ks-border sticky top-0 z-50">
          <div className="max-w-6xl mx-auto px-6 h-12 flex items-center justify-between">
            {/* Left: logo + nav */}
            <div className="flex items-center gap-6">
              <a href="/" className="flex items-center gap-2 shrink-0">
                <div className="w-5 h-5 rounded bg-indigo-600 flex items-center justify-center text-white font-bold select-none" style={{ fontSize: "10px" }}>
                  K
                </div>
                <span className="text-sm font-semibold text-ks-text tracking-tight">Keystone</span>
              </a>
              <div className="h-4 w-px bg-ks-border hidden sm:block" />
              <nav className="hidden sm:flex items-center gap-1">
                <a href="/"
                  className="px-3 py-1.5 rounded-md text-xs font-medium text-ks-text2 hover:text-ks-text hover:bg-ks-hover transition-colors">
                  Transactions
                </a>
              </nav>
            </div>

            {/* Right: status + theme */}
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 dark:bg-emerald-950/50 border border-emerald-200 dark:border-emerald-800/50">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-[11px] font-medium text-emerald-700 dark:text-emerald-400">Live</span>
              </div>
              <div className="w-px h-4 bg-ks-border" />
              <ThemeToggle />
            </div>
          </div>
        </header>
        <main className="max-w-6xl mx-auto px-6 py-6">{children}</main>
      </body>
    </html>
  );
}
