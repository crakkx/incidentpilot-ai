"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export function Nav() {
  const { role, logout } = useAuth();
  const pathname = usePathname();

  const isActive = (path: string) => pathname.startsWith(path);

  return (
    <nav className="sticky top-0 z-50 border-b border-slate-200 bg-white/90 backdrop-blur-md px-6 py-3.5 shadow-sm">
      <div className="mx-auto flex max-w-7xl items-center justify-between">
        {/* Brand Logo */}
        <Link href="/incidents" className="group flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-900 text-white font-black text-sm shadow">
            IP
          </div>
          <div className="flex flex-col">
            <span className="font-extrabold text-base tracking-tight text-slate-900 group-hover:text-indigo-600 transition-colors">
              IncidentPilot <span className="text-indigo-600">AI</span>
            </span>
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest">
              Autonomous RCA Platform
            </span>
          </div>
        </Link>

        {/* Navigation Items */}
        <div className="flex items-center gap-4 text-sm">
          {role && (
            <>
              {(role === "operator" || role === "admin") && (
                <div className="flex items-center gap-1.5">
                  <Link
                    href="/incidents/new"
                    className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                      isActive("/incidents/new")
                        ? "bg-indigo-50 text-indigo-700 border border-indigo-200"
                        : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
                    }`}
                  >
                    + New Incident
                  </Link>

                  <Link
                    href="/approvals"
                    className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                      isActive("/approvals")
                        ? "bg-amber-50 text-amber-800 border border-amber-300"
                        : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
                    }`}
                  >
                    Approvals
                  </Link>

                  <Link
                    href="/ingest"
                    className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                      isActive("/ingest")
                        ? "bg-indigo-50 text-indigo-700 border border-indigo-200"
                        : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
                    }`}
                  >
                    Ingestion
                  </Link>
                </div>
              )}

              {role === "admin" && (
                <Link
                  href="/admin/users"
                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                    isActive("/admin/users")
                      ? "bg-purple-50 text-purple-700 border border-purple-200"
                      : "text-purple-700 hover:text-purple-900 hover:bg-purple-50"
                  }`}
                >
                  Admin RBAC
                </Link>
              )}

              <div className="h-4 w-px bg-slate-200" />

              {/* User Role Badge */}
              <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider text-slate-700">
                {role}
              </span>

              {/* Logout Button */}
              <button
                onClick={logout}
                className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-all"
              >
                Log out
              </button>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
