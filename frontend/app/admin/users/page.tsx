"use client";

import { useEffect, useState } from "react";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { api, UserRead } from "@/lib/api";

function UserManagementContent() {
  const [users, setUsers] = useState<UserRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  // New User Form State
  const [showAddModal, setShowAddModal] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState("operator");
  const [addLoading, setAddLoading] = useState(false);

  // Issue API Key State
  const [showKeyModal, setShowKeyModal] = useState(false);
  const [keyEmail, setKeyEmail] = useState("");
  const [keyRole, setKeyRole] = useState("operator");
  const [issuedKey, setIssuedKey] = useState<string | null>(null);
  const [keyLoading, setKeyLoading] = useState(false);

  const fetchUsers = () => {
    setLoading(true);
    api
      .listUsers()
      .then(setUsers)
      .catch(() => setError("Failed to load user directory."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleRoleChange = async (userId: string, role: string) => {
    setActionMsg(null);
    try {
      const updated = await api.updateUserRole(userId, role);
      setUsers((prev) => prev.map((u) => (u.id === userId ? updated : u)));
      setActionMsg(`Updated user role to ${role}`);
    } catch (err: any) {
      setError(`Failed to update role: ${err.message || err}`);
    }
  };

  const handleStatusToggle = async (userId: string, currentStatus: boolean) => {
    setActionMsg(null);
    try {
      const updated = await api.updateUserStatus(userId, !currentStatus);
      setUsers((prev) => prev.map((u) => (u.id === userId ? updated : u)));
      setActionMsg(`User status updated to ${!currentStatus ? "Active" : "Inactive"}`);
    } catch (err: any) {
      setError(`Failed to update status: ${err.message || err}`);
    }
  };

  const handleDeleteUser = async (userId: string, email: string) => {
    if (!confirm(`Are you sure you want to delete user ${email}?`)) return;
    setActionMsg(null);
    try {
      await api.deleteUser(userId);
      setUsers((prev) => prev.filter((u) => u.id !== userId));
      setActionMsg(`User ${email} deleted.`);
    } catch (err: any) {
      setError(`Failed to delete user: ${err.message || err}`);
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setAddLoading(true);
    setError(null);
    setActionMsg(null);
    try {
      const created = await api.createUser({
        email: newEmail,
        password: newPassword,
        role: newRole,
      });
      setUsers((prev) => [created, ...prev]);
      setActionMsg(`Successfully created user ${created.email}`);
      setShowAddModal(false);
      setNewEmail("");
      setNewPassword("");
    } catch (err: any) {
      setError(`Failed to create user: ${err.message || err}`);
    } finally {
      setAddLoading(false);
    }
  };

  const handleIssueApiKey = async (e: React.FormEvent) => {
    e.preventDefault();
    setKeyLoading(true);
    setError(null);
    setIssuedKey(null);
    try {
      const res = await api.issueApiKey({ email: keyEmail, role: keyRole });
      setIssuedKey(res.api_key);
      fetchUsers();
    } catch (err: any) {
      setError(`Failed to issue API key: ${err.message || err}`);
    } finally {
      setKeyLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">Admin RBAC & User Management</h1>
          <p className="text-xs text-slate-500 font-medium mt-1">
            Manage team accounts, assign RBAC roles (`viewer`, `operator`, `admin`), and issue machine API keys (`ipk_...`).
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              setShowKeyModal(true);
              setIssuedKey(null);
            }}
            className="rounded-lg border border-purple-200 bg-purple-50 px-3.5 py-2 text-xs font-bold text-purple-700 hover:bg-purple-100 transition-all"
          >
            + Issue API Key
          </button>
          <button
            onClick={() => setShowAddModal(true)}
            className="rounded-lg bg-slate-900 px-3.5 py-2 text-xs font-bold text-white shadow hover:bg-slate-800 transition-all"
          >
            + Provision User
          </button>
        </div>
      </div>

      {actionMsg && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-xs font-semibold text-emerald-800">
          {actionMsg}
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs font-semibold text-red-700">
          {error}
        </div>
      )}

      {/* User Directory Table */}
      <div className="glass-card overflow-hidden border border-slate-200 shadow-sm">
        <table className="w-full text-left text-xs text-slate-700">
          <thead className="border-b border-slate-200 bg-slate-50 text-[11px] font-bold uppercase tracking-wider text-slate-500">
            <tr>
              <th className="px-5 py-3.5">User Email</th>
              <th className="px-5 py-3.5">RBAC Role</th>
              <th className="px-5 py-3.5">Account Status</th>
              <th className="px-5 py-3.5">API Key</th>
              <th className="px-5 py-3.5">Created Date</th>
              <th className="px-5 py-3.5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr>
                <td colSpan={6} className="px-5 py-8 text-center text-slate-400">
                  Loading user directory…
                </td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-5 py-8 text-center text-slate-400">
                  No users found in directory.
                </td>
              </tr>
            ) : (
              users.map((u) => (
                <tr key={u.id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-5 py-3.5 font-semibold text-slate-900">{u.email}</td>
                  <td className="px-5 py-3.5">
                    <select
                      value={u.role}
                      onChange={(e) => handleRoleChange(u.id, e.target.value)}
                      className="rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-bold uppercase text-slate-800 focus:border-indigo-500 focus:outline-none"
                    >
                      <option value="viewer">viewer</option>
                      <option value="operator">operator</option>
                      <option value="admin">admin</option>
                    </select>
                  </td>
                  <td className="px-5 py-3.5">
                    <button
                      onClick={() => handleStatusToggle(u.id, u.is_active)}
                      className={`inline-flex rounded-full border px-2.5 py-0.5 text-[10px] font-extrabold uppercase transition-all ${
                        u.is_active
                          ? "border-emerald-200 bg-emerald-50 text-emerald-800 hover:bg-emerald-100"
                          : "border-red-200 bg-red-50 text-red-700 hover:bg-red-100"
                      }`}
                    >
                      {u.is_active ? "Active" : "Inactive"}
                    </button>
                  </td>
                  <td className="px-5 py-3.5">
                    {u.has_api_key ? (
                      <span className="inline-flex rounded border border-purple-200 bg-purple-50 px-2 py-0.5 text-[10px] font-bold text-purple-700 uppercase">
                        Issued
                      </span>
                    ) : (
                      <span className="text-slate-400">—</span>
                    )}
                  </td>
                  <td className="px-5 py-3.5 text-slate-500">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-5 py-3.5 text-right">
                    <button
                      onClick={() => handleDeleteUser(u.id, u.email)}
                      className="text-xs font-bold text-red-600 hover:text-red-800 transition-colors"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Add User Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="glass-card w-full max-w-md p-6 space-y-4 shadow-xl">
            <h2 className="text-lg font-extrabold text-slate-900">Provision New Account</h2>
            <form onSubmit={handleCreateUser} className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600">Email Address</label>
                <input
                  type="email"
                  required
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  placeholder="engineer@company.example"
                  className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs text-slate-900 focus:border-indigo-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600">Password</label>
                <input
                  type="password"
                  required
                  minLength={6}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs text-slate-900 focus:border-indigo-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600">Assigned Role</label>
                <select
                  value={newRole}
                  onChange={(e) => setNewRole(e.target.value)}
                  className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs text-slate-900 focus:border-indigo-500 focus:outline-none"
                >
                  <option value="viewer">Viewer (Read-only)</option>
                  <option value="operator">Operator (Trigger RCA / Remediate)</option>
                  <option value="admin">Admin (Full Access)</option>
                </select>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={addLoading}
                  className="rounded-lg bg-slate-900 px-4 py-2 text-xs font-bold text-white shadow disabled:opacity-50"
                >
                  {addLoading ? "Creating…" : "Create User"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Issue API Key Modal */}
      {showKeyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="glass-card w-full max-w-md p-6 space-y-4 shadow-xl">
            <h2 className="text-lg font-extrabold text-slate-900">Issue Machine API Key</h2>
            <p className="text-xs text-slate-500">
              Generates a long-lived API key (`ipk_...`) for CI/CD pipelines and automated scripts.
            </p>

            {issuedKey ? (
              <div className="space-y-4">
                <div className="rounded-xl border border-purple-200 bg-purple-50 p-4 space-y-2">
                  <span className="block text-[11px] font-bold text-purple-800 uppercase tracking-wider">
                    Plaintext API Key Issued
                  </span>
                  <code className="block break-all font-mono text-xs font-bold text-purple-950 bg-white p-3 rounded-lg border border-purple-200">
                    {issuedKey}
                  </code>
                  <span className="block text-[11px] text-purple-700 font-medium">
                    ⚠️ Copy this key now! The raw key is hashed in PostgreSQL and will not be displayed again.
                  </span>
                </div>
                <button
                  onClick={() => setShowKeyModal(false)}
                  className="w-full rounded-lg bg-slate-900 py-2.5 text-xs font-bold text-white hover:bg-slate-800 shadow"
                >
                  Done
                </button>
              </div>
            ) : (
              <form onSubmit={handleIssueApiKey} className="space-y-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-600">Account Email</label>
                  <input
                    type="email"
                    required
                    value={keyEmail}
                    onChange={(e) => setKeyEmail(e.target.value)}
                    placeholder="ci-bot@company.example"
                    className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs text-slate-900 focus:border-indigo-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-600">Assigned Role</label>
                  <select
                    value={keyRole}
                    onChange={(e) => setKeyRole(e.target.value)}
                    className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs text-slate-900 focus:border-indigo-500 focus:outline-none"
                  >
                    <option value="operator">Operator (Trigger RCA / Remediate)</option>
                    <option value="viewer">Viewer (Read-only)</option>
                    <option value="admin">Admin (Full Access)</option>
                  </select>
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowKeyModal(false)}
                    className="rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={keyLoading}
                    className="rounded-lg bg-purple-700 px-4 py-2 text-xs font-bold text-white shadow hover:bg-purple-800 disabled:opacity-50"
                  >
                    {keyLoading ? "Generating…" : "Generate API Key"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function AdminUsersPage() {
  return (
    <ProtectedRoute allowedRoles={["admin"]}>
      <UserManagementContent />
    </ProtectedRoute>
  );
}
