import { Link, NavLink, Outlet } from "react-router-dom";
import { LayoutDashboard, Store as StoreIcon, FileText } from "lucide-react";

export function Layout() {
  return (
    <div className="flex h-screen bg-bg-black text-ink-primary">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <div className="max-w-6xl mx-auto px-8 py-10">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

function Sidebar() {
  return (
    <aside className="w-56 shrink-0 bg-bg-panel border-r border-white/[0.05] flex flex-col">
      <div className="px-6 py-6 border-b border-white/[0.05]">
        <Link to="/" className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-brand flex items-center justify-center text-white font-emphasis text-sm">
            iX
          </div>
          <span className="text-ink-primary font-emphasis tracking-tight">
            InsightX
          </span>
          <span className="text-[10px] text-ink-subtle font-mono ml-auto">
            v5α
          </span>
        </Link>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-1">
        <NavItem to="/" icon={<LayoutDashboard size={16} />} label="Dashboard" />
        <NavItem to="/stores" icon={<StoreIcon size={16} />} label="Stores" />
        <NavItem to="/reports" icon={<FileText size={16} />} label="Reports" />
      </nav>
      <div className="px-6 py-4 border-t border-white/[0.05] text-[11px] text-ink-subtle">
        <div className="font-mono">dev@insightx.local</div>
      </div>
    </aside>
  );
}

function NavItem({
  to,
  icon,
  label,
}: {
  to: string;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        `flex items-center gap-3 px-3 py-2 rounded-md text-[13px] font-signature transition-colors ${
          isActive
            ? "bg-white/[0.05] text-ink-primary"
            : "text-ink-secondary hover:bg-white/[0.03] hover:text-ink-primary"
        }`
      }
    >
      {icon}
      <span>{label}</span>
    </NavLink>
  );
}
