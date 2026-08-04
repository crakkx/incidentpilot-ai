"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      router.push("/incidents");
    } catch (err) {
      setError(err instanceof ApiError ? "Incorrect email or password." : "Login failed.");
    } finally {
      setSubmitting(false);
    }
  }

  const fillPreset = (roleEmail: string, rolePass: string) => {
    setEmail(roleEmail);
    setPassword(rolePass);
  };

  return (
    <div className="mx-auto mt-12 max-w-md">
      <div className="glass-card p-8 shadow-md border border-slate-200">
        {/* Header */}
        <div className="text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-900 text-white font-black text-lg shadow">
            IP
          </div>
          <h1 className="mt-4 text-2xl font-extrabold tracking-tight text-slate-900">
            IncidentPilot <span className="text-indigo-600">AI</span>
          </h1>
          <p className="mt-1 text-xs text-slate-500 font-medium">
            Sign in to access your SRE Autonomous Command Center
          </p>
        </div>

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600">
              Email Address
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 transition-all"
              placeholder="operator@incidentpilot.example"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600">
              Password
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 transition-all"
              placeholder="••••••••"
            />
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs font-semibold text-red-700">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-slate-900 py-3 text-xs font-bold text-white shadow hover:bg-slate-800 disabled:opacity-50 transition-all active:scale-[0.99]"
          >
            {submitting ? "Authenticating…" : "Sign In to Dashboard"}
          </button>
        </form>

        {/* Demo Credentials Quick Fill */}
        <div className="mt-8 border-t border-slate-100 pt-5">
          <span className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-2.5 text-center">
            Quick Fill Demo Accounts
          </span>
          <div className="grid grid-cols-3 gap-2">
            <button
              type="button"
              onClick={() => fillPreset("admin@incidentpilot.example", "admin123")}
              className="rounded-lg border border-purple-200 bg-purple-50 py-1.5 text-xs font-medium text-purple-700 hover:bg-purple-100 transition-all"
            >
              Admin
            </button>
            <button
              type="button"
              onClick={() => fillPreset("operator@incidentpilot.example", "op123")}
              className="rounded-lg border border-indigo-200 bg-indigo-50 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100 transition-all"
            >
              Operator
            </button>
            <button
              type="button"
              onClick={() => fillPreset("viewer@incidentpilot.example", "view123")}
              className="rounded-lg border border-slate-200 bg-slate-100 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-200 transition-all"
            >
              Viewer
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
