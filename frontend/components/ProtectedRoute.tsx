"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export function ProtectedRoute({
  children,
  allowedRoles,
}: {
  children: React.ReactNode;
  allowedRoles?: string[];
}) {
  const { role, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading) {
      if (!role) {
        router.replace("/login");
      } else if (allowedRoles && !allowedRoles.includes(role)) {
        router.replace("/incidents");
      }
    }
  }, [loading, role, router, allowedRoles]);

  if (loading || !role || (allowedRoles && !allowedRoles.includes(role))) {
    return <div className="p-8 text-slate-500">Loading…</div>;
  }

  return <>{children}</>;
}
