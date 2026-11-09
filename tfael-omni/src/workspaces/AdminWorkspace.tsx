// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Admin Workspace (Tailwind migration)
// 3 inner tabs: User Management, RBAC Matrix, Audit Log
// ═══════════════════════════════════════════════════════════════════════

import { useState } from 'react';
import { SubTabs } from '@/components/ui/Tabs/Tabs';
import { UserManagement } from '@/components/admin/UserManagement/UserManagement';
import { RbacMatrix } from '@/components/admin/RBACMatrix/RbacMatrix';
import { AuditLog } from '@/components/admin/AuditLog/AuditLog';

type AdminTab = 'users' | 'rbac' | 'audit';

const INNER_TABS = [
  { id: 'users', label: 'User Management' },
  { id: 'rbac',  label: 'RBAC Matrix' },
  { id: 'audit', label: 'Audit Log' },
];

export default function AdminWorkspace() {
  const [tab, setTab] = useState<AdminTab>('users');

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <SubTabs
        tabs={INNER_TABS}
        active={tab}
        onChange={id => setTab(id as AdminTab)}
      />

      <div className="flex-1 overflow-auto">
        {tab === 'users' && <UserManagement />}
        {tab === 'rbac' && <RbacMatrix />}
        {tab === 'audit' && <AuditLog />}
      </div>
    </div>
  );
}
