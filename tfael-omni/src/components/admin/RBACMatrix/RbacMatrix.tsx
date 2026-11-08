// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — RBAC Permission Matrix (Tailwind migration)
// Interactive role × permission toggle grid
// ═══════════════════════════════════════════════════════════════════════

import { useState, useEffect, useCallback } from 'react';
import type { RolePermission } from '@/types/api';
import { adminListRoles, adminUpdateRole } from '@/api/endpoints';
import { useToast } from '@/hooks/useToast';

// Backend returns { roles: string[], permissions: [[key,label],...], matrix: {role: {perm: bool}} }
// Transform to RolePermission[] for the grid
interface PermInfo { key: string; label: string }

export function RbacMatrix() {
  const [roles, setRoles] = useState<RolePermission[]>([]);
  const [permList, setPermList] = useState<PermInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  const loadRoles = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminListRoles();
      if (res.ok && res.matrix) {
        const perms: PermInfo[] = (res.permissions ?? []).map(([key, label]) => ({ key, label }));
        setPermList(perms);
        const roleList: RolePermission[] = (res.roles ?? []).map((roleName: string) => ({
          role: roleName,
          permissions: res.matrix[roleName] ?? {},
        }));
        setRoles(roleList);
      }
    } catch { /* swallow */ }
    setLoading(false);
  }, []);

  useEffect(() => { loadRoles(); }, [loadRoles]);

  const handleToggle = useCallback(async (role: string, perm: string, current: boolean) => {
    try {
      const res = await adminUpdateRole(role, perm, !current);
      if (res.ok) {
        toast(`${role}.${perm} = ${!current}`, 'success');
        loadRoles();
      } else {
        toast('Gagal update permission', 'error');
      }
    } catch { toast('Gagal update permission', 'error'); }
  }, [toast, loadRoles]);

  if (loading) return <div className="p-3"><div className="text-center py-10 px-4 opacity-40 text-[13px] font-mono">⏳ Loading RBAC…</div></div>;
  if (roles.length === 0) return <div className="p-3"><div className="text-center py-10 px-4 opacity-40 text-[13px] font-mono">Tidak ada data role</div></div>;

  // Use permission list from backend (preserves order + labels)
  const allPermissions = permList.length > 0
    ? permList
    : [...new Set(roles.flatMap(r => Object.keys(r.permissions)))].sort().map(k => ({ key: k, label: k }));

  return (
    <div className="p-3 overflow-x-auto">
      <table className="w-full border-collapse font-mono text-[11px]">
        <thead>
          <tr>
            <th className="py-2 px-2.5 text-[9px] uppercase tracking-[0.06em] border-b border-border-dim text-left opacity-50 font-bold">
              Permission
            </th>
            {roles.map(r => (
              <th key={r.role} className="py-2 px-2.5 text-[9px] uppercase tracking-[0.06em] border-b border-border-dim text-center opacity-50 font-bold">
                {r.role}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {allPermissions.map(p => (
            <tr key={p.key} className="border-b border-white/[0.03] hover:bg-background-hover transition-colors">
              <td className="py-1.5 px-2.5 text-left font-bold uppercase text-2xs" title={p.key}>
                {p.label || p.key.replace(/_/g, ' ')}
              </td>
              {roles.map(r => {
                const val = !!r.permissions[p.key];
                return (
                  <td key={r.role} className="py-1.5 px-2.5 text-center">
                    <input
                      type="checkbox"
                      className="w-[18px] h-[18px] cursor-pointer accent-[#10b981]"
                      checked={val}
                      onChange={() => handleToggle(r.role, p.key, val)}
                    />
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
