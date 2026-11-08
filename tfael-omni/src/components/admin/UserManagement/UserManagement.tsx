// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — User Management (Tailwind migration)
// CRUD for platform users + role assignment
// ═══════════════════════════════════════════════════════════════════════

import { useState, useEffect, useCallback } from 'react';
import { cn } from '@/lib/utils';
import type { AdminUser } from '@/types/api';
import {
  adminListUsers, adminCreateUser, adminUpdateUser,
  adminResetPassword, adminDeleteUser,
} from '@/api/endpoints';
import { useToast } from '@/hooks/useToast';

const ROLES = ['KOMANDAN', 'ADMIN', 'OPERATOR', 'ANALIS', 'AUDITOR'];

// Backend returns status:"AKTIF"/"NONAKTIF" — map to AdminUser.active boolean
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function normalizeUser(raw: any): AdminUser {
  return {
    user_id:    raw.user_id ?? '',
    username:   raw.username ?? '',
    role:       (raw.role ?? 'AUDITOR').toUpperCase(),
    active:     typeof raw.active === 'boolean'
                  ? raw.active
                  : (raw.status ?? '').toUpperCase() === 'AKTIF',
    created_at: raw.created_at ?? '',
    last_login: raw.last_login ?? undefined,
    full_name:  raw.full_name,
    rank_title: raw.rank_title,
  };
}

// ── Role badge classes ───────────────────────────────────────────────
const ROLE_CLS: Record<string, string> = {
  ADMIN:    'bg-[rgba(239,68,68,0.15)] text-[#fca5a5]',
  KOMANDAN: 'bg-[rgba(239,68,68,0.15)] text-[#fca5a5]',
  OPERATOR: 'bg-[rgba(34,211,238,0.15)] text-[#67e8f9]',
  ANALIS:   'bg-[rgba(167,139,250,0.15)] text-[#c4b5fd]',
  AUDITOR:  'bg-[rgba(148,163,184,0.15)] text-[#cbd5e1]',
};
const ROLE_DEFAULT = 'bg-[rgba(148,163,184,0.15)] text-[#cbd5e1]';

// ── Shared class strings ─────────────────────────────────────────────
const FORM_INPUT = 'flex-1 py-[5px] px-2.5 bg-background-deep border border-border-dim rounded font-mono text-xs text-inherit focus:outline-none focus:border-accent-steel';
const ACTION_BTN = 'py-[3px] px-2 border border-border-dim rounded bg-transparent text-inherit font-mono text-2xs cursor-pointer transition-all hover:border-border-accent';
const DANGER_BTN = `${ACTION_BTN} !border-[rgba(239,68,68,0.3)] !text-[#fca5a5] hover:!bg-[rgba(239,68,68,0.1)]`;

export function UserManagement() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [newUser, setNewUser] = useState({ username: '', full_name: '', rank_title: '', role: 'OPERATOR' });
  const { toast } = useToast();

  const loadUsers = useCallback(async () => {
    try {
      const res = await adminListUsers();
      if (res.ok) setUsers((res.rows ?? res.users ?? []).map(normalizeUser));
    } catch { /* swallow */ }
  }, []);

  useEffect(() => { loadUsers(); }, [loadUsers]);

  const handleCreate = useCallback(async () => {
    if (!newUser.username) {
      toast('Username wajib diisi', 'error');
      return;
    }
    try {
      const res = await adminCreateUser({
        username: newUser.username,
        full_name: newUser.full_name,
        rank_title: newUser.rank_title,
        role: newUser.role,
      });
      if (res.ok) {
        const msg = res.temp_password
          ? `User "${newUser.username}" dibuat. Password sementara: ${res.temp_password}`
          : `User "${newUser.username}" dibuat`;
        toast(msg, 'success');
        setNewUser({ username: '', full_name: '', rank_title: '', role: 'OPERATOR' });
        setShowCreate(false);
        loadUsers();
      } else {
        toast(res.error ?? 'Gagal membuat user', 'error');
      }
    } catch { toast('Gagal membuat user', 'error'); }
  }, [newUser, toast, loadUsers]);

  const handleToggleActive = useCallback(async (user: AdminUser) => {
    try {
      const newStatus = user.active ? 'NONAKTIF' : 'AKTIF';
      const res = await adminUpdateUser({ user_id: user.user_id, status: newStatus });
      if (res.ok) {
        toast(`User "${user.username}" ${user.active ? 'dinonaktifkan' : 'diaktifkan'}`, 'success');
        loadUsers();
      }
    } catch { toast('Gagal update user', 'error'); }
  }, [toast, loadUsers]);

  const handleChangeRole = useCallback(async (userId: string, role: string) => {
    try {
      const res = await adminUpdateUser({ user_id: userId, role });
      if (res.ok) { toast(`Role diubah ke ${role}`, 'success'); loadUsers(); }
    } catch { toast('Gagal ubah role', 'error'); }
  }, [toast, loadUsers]);

  const handleResetPw = useCallback(async (userId: string, username: string) => {
    if (!confirm(`Reset password untuk ${username}?`)) return;
    try {
      const res = await adminResetPassword(userId);
      if (res.ok) {
        toast(`Password direset${res.temp_password ? `: ${res.temp_password}` : ''}`, 'success');
      } else toast('Gagal reset password', 'error');
    } catch { toast('Gagal reset password', 'error'); }
  }, [toast]);

  const handleDelete = useCallback(async (userId: string, username: string) => {
    if (!confirm(`Hapus user "${username}"?`)) return;
    try {
      const res = await adminDeleteUser(userId);
      if (res.ok) { toast(`User "${username}" dihapus`, 'success'); loadUsers(); }
      else toast('Gagal hapus user', 'error');
    } catch { toast('Gagal hapus user', 'error'); }
  }, [toast, loadUsers]);

  const fmtDate = (ts: string | undefined) => {
    if (!ts) return '—';
    try {
      return new Date(ts).toLocaleString('id-ID', {
        day: '2-digit', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
      });
    } catch { return ts; }
  };

  return (
    <div className="p-3">
      <div className="flex items-center gap-2 mb-3">
        <button
          className="py-[5px] px-3.5 border border-[#10b981] rounded bg-transparent text-[#10b981] font-mono text-[11px] cursor-pointer transition-all hover:bg-[#10b981] hover:text-black"
          onClick={() => setShowCreate(v => !v)}
        >
          {showCreate ? '✕ Batal' : '+ Tambah User'}
        </button>
        <button
          className="py-[5px] px-3 border border-border-dim rounded bg-transparent text-inherit font-mono text-[11px] cursor-pointer hover:border-border-accent"
          onClick={loadUsers}
        >
          🔄 Refresh
        </button>
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="mb-3.5 p-3.5 bg-background-card border border-border-dim rounded-lg">
          <div className="text-[13px] font-bold font-mono mb-2.5">Tambah User Baru</div>
          <div className="flex items-center gap-2 mb-2 font-mono text-xs">
            <span className="min-w-[110px] text-2xs uppercase opacity-50">Username</span>
            <input className={FORM_INPUT} value={newUser.username}
              onChange={e => setNewUser(p => ({ ...p, username: e.target.value }))} />
          </div>
          <div className="flex items-center gap-2 mb-2 font-mono text-xs">
            <span className="min-w-[110px] text-2xs uppercase opacity-50">Nama Lengkap</span>
            <input className={FORM_INPUT} value={newUser.full_name}
              onChange={e => setNewUser(p => ({ ...p, full_name: e.target.value }))} />
          </div>
          <div className="flex items-center gap-2 mb-2 font-mono text-xs">
            <span className="min-w-[110px] text-2xs uppercase opacity-50">Pangkat/Jabatan</span>
            <input className={FORM_INPUT} value={newUser.rank_title}
              onChange={e => setNewUser(p => ({ ...p, rank_title: e.target.value }))} />
          </div>
          <div className="flex items-center gap-2 mb-2 font-mono text-xs">
            <span className="min-w-[110px] text-2xs uppercase opacity-50">Role</span>
            <select className={cn(FORM_INPUT, 'cursor-pointer')} value={newUser.role}
              onChange={e => setNewUser(p => ({ ...p, role: e.target.value }))}>
              {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          <div className="mt-2.5">
            <button
              className="py-[5px] px-3.5 border border-[#10b981] rounded bg-transparent text-[#10b981] font-mono text-[11px] cursor-pointer transition-all hover:bg-[#10b981] hover:text-black"
              onClick={handleCreate}
            >
              ✓ Buat User
            </button>
          </div>
        </div>
      )}

      {/* User table */}
      {users.length === 0 ? (
        <div className="text-center py-10 px-4 opacity-30 text-[13px] font-mono">
          Belum ada user terdaftar
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse font-mono text-xs">
            <thead>
              <tr>
                {['Username', 'Role', 'Status', 'Created', 'Last Login', 'Actions'].map(h => (
                  <th key={h} className="py-2 px-2.5 text-[9px] uppercase tracking-[0.06em] border-b border-border-dim text-left opacity-50 font-bold">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.username} className="border-b border-white/[0.03] hover:bg-background-hover transition-colors">
                  <td className="py-2 px-2.5">
                    <div>{u.username}</div>
                    {u.full_name && (
                      <div className="text-2xs opacity-50">
                        {u.rank_title ? `${u.rank_title} — ` : ''}{u.full_name}
                      </div>
                    )}
                  </td>
                  <td className="py-2 px-2.5">
                    <select
                      className={cn(
                        'py-0.5 px-2 rounded-[3px] text-2xs font-bold uppercase border-none bg-transparent cursor-pointer',
                        ROLE_CLS[u.role.toUpperCase()] ?? ROLE_DEFAULT,
                      )}
                      value={u.role}
                      onChange={e => handleChangeRole(u.user_id, e.target.value)}
                    >
                      {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </td>
                  <td className="py-2 px-2.5">
                    <span className={cn('text-2xs font-bold', u.active ? 'text-[#22c55e]' : 'text-[#ef4444]')}>
                      {u.active ? 'ACTIVE' : 'INACTIVE'}
                    </span>
                  </td>
                  <td className="py-2 px-2.5 text-2xs opacity-50">{fmtDate(u.created_at)}</td>
                  <td className="py-2 px-2.5 text-2xs opacity-50">{fmtDate(u.last_login)}</td>
                  <td className="py-2 px-2.5">
                    <div className="flex gap-1">
                      <button className={ACTION_BTN} onClick={() => handleToggleActive(u)}>
                        {u.active ? '⏸' : '▶'}
                      </button>
                      <button className={ACTION_BTN} onClick={() => handleResetPw(u.user_id, u.username)}>🔑</button>
                      <button className={DANGER_BTN} onClick={() => handleDelete(u.user_id, u.username)}>🗑</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
