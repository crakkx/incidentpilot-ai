import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { Nav } from "@/components/Nav";

export const metadata: Metadata = {
  title: "IncidentPilot AI — SRE Autonomous Command",
  description: "Agentic incident root-cause analysis and investigation platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-slate-50 text-slate-900 antialiased">
        <AuthProvider>
          <Nav />
          <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
