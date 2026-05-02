import { useParams } from "react-router-dom";
import { useState } from "react";
import { ArrowLeft, Play, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";

import {
  useStore,
  useReviews,
  useAnalysisRuns,
  useAddSource,
  useFireScrape,
  useFireAnalysis,
  useJob,
  useAnalysisRun,
} from "../api/hooks";
import { StatusPill } from "../components/StatusPill";

export function StoreDetailPage() {
  const { id } = useParams<{ id: string }>();
  const storeId = Number(id);

  const { data: store } = useStore(storeId);
  const { data: reviews = [] } = useReviews(storeId, 50);
  const { data: runs = [] } = useAnalysisRuns(storeId);
  const addSource = useAddSource(storeId);
  const fireScrape = useFireScrape(storeId);
  const fireAnalysis = useFireAnalysis(storeId);

  const [sourceUrl, setSourceUrl] = useState("");
  const [activeJobId, setActiveJobId] = useState<number | null>(null);
  const [activeRunId, setActiveRunId] = useState<number | null>(null);

  const { data: activeJob } = useJob(activeJobId ?? 0);
  const { data: activeRun } = useAnalysisRun(activeRunId ?? 0);

  if (!store) return <div className="text-ink-muted">載入中…</div>;

  async function handleAddSource() {
    if (!sourceUrl.trim()) return;
    await addSource.mutateAsync({
      source_type: store!.platform === "youtube" ? "youtube" : "google_maps",
      external_url: sourceUrl,
    });
    setSourceUrl("");
  }

  async function handleScrape() {
    const job = await fireScrape.mutateAsync();
    setActiveJobId(job.id);
  }

  async function handleAnalyze() {
    const run = await fireAnalysis.mutateAsync({ ai_function: "analyze" });
    setActiveRunId(run.id);
  }

  return (
    <div className="space-y-8">
      <Link to="/" className="text-[13px] text-ink-muted hover:text-ink-primary inline-flex items-center gap-2">
        <ArrowLeft size={14} /> 回 Dashboard
      </Link>

      <header className="flex items-start justify-between">
        <div>
          <h1 className="display-lg">{store.name}</h1>
          <div className="flex items-center gap-3 mt-3 text-[13px] text-ink-muted">
            <span className="pill text-[11px]">{store.platform}</span>
            {store.address && <span>{store.address}</span>}
            <span className="font-mono text-ink-subtle">#{store.id}</span>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            className="btn-ghost flex items-center gap-2"
            onClick={handleScrape}
            disabled={fireScrape.isPending}
          >
            <Play size={14} /> Scrape
          </button>
          <button
            className="btn-primary flex items-center gap-2"
            onClick={handleAnalyze}
            disabled={fireAnalysis.isPending || reviews.length === 0}
          >
            <Sparkles size={14} /> Analyze
          </button>
        </div>
      </header>

      {/* Add source */}
      <section className="surface-card p-5">
        <h3 className="heading-3 mb-3">Review Source</h3>
        <div className="flex gap-2">
          <input
            value={sourceUrl}
            onChange={(e) => setSourceUrl(e.target.value)}
            placeholder={
              store.platform === "youtube"
                ? "貼 YouTube 影片網址"
                : "貼 Google Maps 店家網址"
            }
            className="flex-1 bg-white/[0.02] border border-white/[0.08] rounded px-3 py-2 text-[14px] text-ink-primary placeholder:text-ink-subtle focus:outline-none focus:border-brand-accent"
          />
          <button
            className="btn-ghost"
            onClick={handleAddSource}
            disabled={!sourceUrl.trim() || addSource.isPending}
          >
            {addSource.isPending ? "新增中…" : "加入 source"}
          </button>
        </div>
      </section>

      {/* Active job progress */}
      {activeJob && (
        <section className="surface-card p-5">
          <div className="flex items-center justify-between mb-2">
            <h3 className="heading-3">Scrape Job #{activeJob.id}</h3>
            <StatusPill status={activeJob.status} />
          </div>
          <div className="text-[13px] text-ink-muted">
            已抓 <span className="text-ink-primary font-mono">{activeJob.reviews_fetched_count}</span> 則評論
            {activeJob.pagination_truncated && " · ⚠️ 部分評論未抓完（pagination truncated）"}
          </div>
          {activeJob.error_message && (
            <div className="text-[13px] text-error mt-2 font-mono">{activeJob.error_message}</div>
          )}
        </section>
      )}

      {activeRun && (
        <section className="surface-card p-5">
          <div className="flex items-center justify-between mb-2">
            <h3 className="heading-3">
              Analysis Run #{activeRun.id} <span className="text-ink-muted font-normal">— {activeRun.ai_function}</span>
            </h3>
            <StatusPill status={activeRun.status} />
          </div>
          {activeRun.output_json && activeRun.status === "succeeded" && (
            <pre className="text-[12px] text-ink-secondary bg-white/[0.02] p-4 rounded mt-3 overflow-x-auto font-mono">
              {JSON.stringify(activeRun.output_json, null, 2).slice(0, 1500)}
            </pre>
          )}
          {activeRun.error_message && (
            <div className="text-[13px] text-error mt-2 font-mono">{activeRun.error_message}</div>
          )}
        </section>
      )}

      {/* Analysis history */}
      <section>
        <h3 className="heading-3 mb-4">分析歷史 ({runs.length})</h3>
        {runs.length === 0 ? (
          <div className="text-ink-muted text-[14px]">尚無分析紀錄。先 Scrape 再 Analyze。</div>
        ) : (
          <div className="space-y-2">
            {runs.slice(0, 10).map((r) => (
              <div key={r.id} className="surface-card p-4 flex items-center justify-between">
                <div>
                  <div className="font-signature text-[14px]">
                    <span className="font-mono text-ink-subtle text-[11px]">#{r.id}</span>{" "}
                    {r.ai_function}
                  </div>
                  <div className="text-[11px] text-ink-muted mt-1 font-mono">
                    {r.model_id} · {r.prompt_version} · {new Date(r.created_at).toLocaleString("zh-TW")}
                  </div>
                </div>
                <StatusPill status={r.status} />
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Recent reviews */}
      <section>
        <h3 className="heading-3 mb-4">最近評論 ({reviews.length})</h3>
        {reviews.length === 0 ? (
          <div className="text-ink-muted text-[14px]">還沒抓過評論。</div>
        ) : (
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {reviews.slice(0, 30).map((r) => (
              <div key={r.id} className="surface-card p-3">
                <div className="flex items-start gap-3">
                  {r.rating != null && (
                    <span className="text-[12px] text-warning font-mono shrink-0">
                      {"★".repeat(r.rating)}
                    </span>
                  )}
                  <div className="flex-1 min-w-0">
                    {r.author && (
                      <div className="text-[11px] text-ink-subtle mb-1 font-mono">{r.author}</div>
                    )}
                    <div className="text-[13px] text-ink-secondary line-clamp-3">{r.text}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
