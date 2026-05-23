"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { useRouter, usePathname } from "next/navigation";
import { authMe, getStoredEmployeeId, setStoredEmployeeId } from "@/lib/api";

export type EmployeeProfile = {
  employee_id: string;
  name: string;
  email: string;
  designation: string;
  department: string;
  authorized_tools: string;
  is_admin: boolean;
  memberships: Array<{ workspace_id: string; role: string; workspace_name: string }>;
  owned_agents: Array<{ agent_id: string; name: string; workspace_id: string | null }>;
  collaborator_agents: Array<{ agent_id: string; name: string; workspace_id: string | null; role: string }>;
  visible_workspace_ids: string[] | null; // null = admin (unrestricted)
  pending_requests_as_admin: number;
  my_pending_requests: Array<{ workspace_id: string; workspace_name: string; role: string; status: string; requested_at: string }>;
};

type AuthCtx = {
  me: EmployeeProfile | null;
  loading: boolean;
  logout: () => void;
  canSeeWorkspace: (workspaceId: string | null | undefined) => boolean;
  canApprove: (args: {
    workspace_id: string | null | undefined;
    agent_id: string | null | undefined;
    tool: string | null | undefined;
  }) => { allowed: boolean; reason: string };
};

const AuthContext = createContext<AuthCtx>({
  me: null,
  loading: true,
  logout: () => {},
  canSeeWorkspace: () => true,
  canApprove: () => ({ allowed: false, reason: "Not signed in" }),
});

const PUBLIC_ROUTES = new Set(["/login"]);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<EmployeeProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    let alive = true;
    const storedId = getStoredEmployeeId();
    if (!storedId) {
      setLoading(false);
      if (!PUBLIC_ROUTES.has(pathname)) router.replace("/login");
      return;
    }
    authMe()
      .then((profile) => {
        if (!alive) return;
        if (profile) {
          setMe(profile);
        } else {
          setStoredEmployeeId(null);
          if (!PUBLIC_ROUTES.has(pathname)) router.replace("/login");
        }
      })
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [pathname, router]);

  const logout = () => {
    setStoredEmployeeId(null);
    setMe(null);
    router.replace("/login");
  };

  const canSeeWorkspace = (workspaceId: string | null | undefined) => {
    if (!me) return false;
    if (me.is_admin) return true;
    if (!workspaceId) return false;
    return (me.visible_workspace_ids || []).includes(workspaceId);
  };

  const canApprove: AuthCtx["canApprove"] = ({ workspace_id, agent_id, tool }) => {
    if (!me) return { allowed: false, reason: "Not signed in" };

    // Tool scope check (mirrors backend's authorized_tools)
    const authorized = me.authorized_tools || "";
    if (authorized !== "*" && tool) {
      const scopes = authorized.split(",").map((s) => s.trim());
      if (!scopes.includes(tool)) {
        return { allowed: false, reason: `Not authorized for tool '${tool}'` };
      }
    }

    // Owner of the agent (bypasses workspace check)
    if (agent_id && me.owned_agents.some((a) => a.agent_id === agent_id)) {
      return { allowed: true, reason: `Owner of agent ${agent_id}` };
    }

    // Explicit collaborator on the agent (added by admin)
    if (agent_id && me.collaborator_agents?.some((a) => a.agent_id === agent_id)) {
      return { allowed: true, reason: "Agent collaborator" };
    }

    if (!workspace_id) {
      return { allowed: false, reason: "Action has no workspace context" };
    }

    // Must be a member of the action's workspace
    const m = me.memberships.find((x) => x.workspace_id === workspace_id);
    if (!m) return { allowed: false, reason: "Not a member of this workspace" };

    // Within workspace: admin overrides role, non-admins need admin/approver role
    if (me.is_admin) return { allowed: true, reason: `Admin in workspace (role: ${m.role})` };
    if (m.role === "admin" || m.role === "approver") {
      return { allowed: true, reason: `Workspace ${m.role}` };
    }
    return { allowed: false, reason: `Workspace role '${m.role}' cannot approve` };
  };

  return (
    <AuthContext.Provider value={{ me, loading, logout, canSeeWorkspace, canApprove }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
