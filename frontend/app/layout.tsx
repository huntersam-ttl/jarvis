import type { Metadata } from "next";
import Nav from "@/components/Nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "Jarvis — Control Room",
  description: "Personal AI control system",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body>
        <div className="ambient" aria-hidden>
          <div className="ambient-orb ambient-orb-a" />
          <div className="ambient-orb ambient-orb-b" />
          <div className="ambient-orb ambient-orb-c" />
        </div>
        <div className="flex min-h-screen flex-col md:flex-row">
          <Nav />
          <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8 md:py-8">
            <div className="mx-auto max-w-5xl">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
