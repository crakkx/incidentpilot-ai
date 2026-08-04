"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export default function HomePage() {
  const { role, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    router.replace(role ? "/incidents" : "/login");
  }, [loading, role, router]);

  return (
    <div className="flex h-64 items-center justify-center">
      <div className="flex items-center gap-3 glass-card px-6 py-4">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-cyan-400 border-t-transparent" />
        <span className="text-xs font-semibold text-slate-300">Initializing SRE Command Center…</span>
      </div>
    </div>
  );
}
