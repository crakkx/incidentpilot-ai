"use client";

import Link from "next/link";
import { usePathname, useParams } from "next/navigation";
import { ProtectedRoute } from "@/components/ProtectedRoute";

const TABS = [
  { slug: "timeline", label: "Evidence timeline" },
  { slug: "report", label: "RCA report" },
  { slug: "trace", label: "Investigation trace" },
];

function IncidentTabs({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const params = useParams();
  const id = params.id as string;

  return (
    <div>
      <div className="mb-6 flex gap-1 border-b border-slate-200">
        {TABS.map((tab) => {
          const href = `/incidents/${id}/${tab.slug}`;
          const active = pathname === href;
          return (
            <Link
              key={tab.slug}
              href={href}
              className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
                active
                  ? "border-slate-900 text-slate-900"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              {tab.label}
            </Link>
          );
        })}
      </div>
      {children}
    </div>
  );
}

export default function IncidentLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute>
      <IncidentTabs>{children}</IncidentTabs>
    </ProtectedRoute>
  );
}
