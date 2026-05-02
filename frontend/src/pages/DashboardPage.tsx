import { Link } from "react-router-dom";
import { Plus, MapPin, Youtube } from "lucide-react";
import { useState } from "react";

import { useStores, useCreateStore, useWorkspaces, useCreateWorkspace } from "../api/hooks";

export function DashboardPage() {
  const { data: stores = [], isLoading } = useStores();
  const { data: workspaces = [] } = useWorkspaces();
  const createStore = useCreateStore();
  const createWorkspace = useCreateWorkspace();

  const [showAdd, setShowAdd] = useState(false);
  const [name, setName] = useState("");
  const [platform, setPlatform] = useState<"google" | "youtube">("google");

  async function handleAdd() {
    let wsId = workspaces[0]?.id;
    if (!wsId) {
      const ws = await createWorkspace.mutateAsync("Default Workspace");
      wsId = ws.id;
    }
    if (!name.trim()) return;
    await createStore.mutateAsync({ workspace_id: wsId, name, platform });
    setName("");
    setShowAdd(false);
  }

  return (
    <div className="space-y-8">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="display-lg">Dashboard</h1>
          <p className="text-ink-muted mt-2 text-[15px]">
            Persistent multi-store insight workspace
          </p>
        </div>
        <button className="btn-primary flex items-center gap-2" onClick={() => setShowAdd(!showAdd)}>
          <Plus size={16} /> 新增店家
        </button>
      </header>

      {showAdd && (
        <div className="surface-card p-5 space-y-4">
          <h3 className="heading-3">新增店家</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-[12px] text-ink-muted block mb-2 font-signature">店名</label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full bg-white/[0.02] border border-white/[0.08] rounded px-3 py-2 text-[14px] text-ink-primary placeholder:text-ink-subtle focus:outline-none focus:border-brand-accent"
                placeholder="例如：Pizza Shalom"
              />
            </div>
            <div>
              <label className="text-[12px] text-ink-muted block mb-2 font-signature">平台</label>
              <div className="flex gap-2">
                <button
                  className={`btn-ghost flex-1 flex items-center justify-center gap-2 ${platform === "google" ? "!bg-brand !text-white !border-brand" : ""}`}
                  onClick={() => setPlatform("google")}
                >
                  <MapPin size={14} /> Google
                </button>
                <button
                  className={`btn-ghost flex-1 flex items-center justify-center gap-2 ${platform === "youtube" ? "!bg-brand !text-white !border-brand" : ""}`}
                  onClick={() => setPlatform("youtube")}
                >
                  <Youtube size={14} /> YouTube
                </button>
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button className="btn-ghost" onClick={() => setShowAdd(false)}>
              取消
            </button>
            <button
              className="btn-primary"
              onClick={handleAdd}
              disabled={!name.trim() || createStore.isPending}
            >
              {createStore.isPending ? "建立中…" : "建立"}
            </button>
          </div>
        </div>
      )}

      <section>
        <h2 className="heading-3 mb-4">我的店家 ({stores.length})</h2>
        {isLoading ? (
          <div className="text-ink-muted text-[14px]">載入中…</div>
        ) : stores.length === 0 ? (
          <div className="surface-card p-10 text-center">
            <p className="text-ink-muted text-[14px]">
              還沒有店家。點上方「新增店家」開始追蹤評論。
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {stores.map((s) => (
              <Link
                key={s.id}
                to={`/stores/${s.id}`}
                className="surface-card p-5 transition-colors group"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="font-emphasis text-[16px] text-ink-primary group-hover:text-brand-accent transition-colors">
                    {s.name}
                  </div>
                  <span className="pill text-[10px]">
                    {s.platform === "google" ? "Maps" : "YouTube"}
                  </span>
                </div>
                {s.address && (
                  <div className="text-[12px] text-ink-muted line-clamp-1">{s.address}</div>
                )}
                <div className="text-[11px] text-ink-subtle mt-3 font-mono">
                  #{s.id} · {new Date(s.created_at).toLocaleDateString("zh-TW")}
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
