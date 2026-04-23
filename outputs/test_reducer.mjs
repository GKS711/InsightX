/**
 * P3.11 後 reducer + adapter terminal action shape 回歸測試（48 case，六輪 Codex peer review 後鎖定）
 *
 * 跑法：
 *   cd /Users/gankaisheng/VScode/Claude實作/InsightX
 *   node outputs/test_reducer.mjs
 *
 * 涵蓋：
 *   - SWITCH_PLATFORM / SWITCH_YT_ROLE 變動 / 同值 → reset / 不 reset 下游
 *   - FETCH_ANALYZE_START → analyze=loading + 下游 reset
 *   - FETCH_ANALYZE_SUCCEEDED 不被 stale check 丟棄
 *   - STREAM_START / STREAM_PROGRESS / STREAM_RESULT / STREAM_FAILED / STREAM_CONNECTION_LOST 完整路徑
 *   - case 11a：STREAM_CONNECTION_LOST 必帶 requestId + errorVM.requestId 對齊（ROUND-3-3 內部 requestId 鎖點）
 *   - case 11b/11c：terminal action shape — STREAM_RESULT / STREAM_FAILED 帶 requestId
 *   - case 11d/11e：result/failed payload malformed JSON → 走 onConnectionError，外層 action.requestId 與內層 errorVM.requestId 雙重鎖點（ROUND-4-5 + ROUND-5-3）
 *   - case 11f：openSSE 沒帶 opts.requestId → errorVM.requestId 必為 null（ROUND-4-4 防 runId 偽裝 requestId）
 */
import { reduceAppState, createInitialState } from "../src/static/v2/hooks/useAppReducer.js";

// Stub React for the hook import (測試不會走到 useReducer / useEffect)
globalThis.React = { useReducer: () => [], useEffect: () => {} };

let pass = 0, fail = 0;
const t = (label, ok, info = "") => {
  if (ok) { pass++; console.log("✅", label); }
  else { fail++; console.log("❌", label, info); }
};

// ---- 1. SWITCH_PLATFORM 真的改變 → reset 下游 + analyze ----
let s = createInitialState();
s.features.swot = { status: "ready", requestId: "r1", data: { foo: 1 }, error: null };
s.features.analyze = { status: "ready", requestId: "a1", data: { foo: 1 }, error: null };
s.mode.currentPlatform = "google";
s = reduceAppState(s, { type: "SWITCH_PLATFORM", platform: "youtube" });
t("SWITCH_PLATFORM (google→youtube) resets swot to idle", s.features.swot.status === "idle");
t("SWITCH_PLATFORM resets analyze to idle", s.features.analyze.status === "idle");
t("SWITCH_PLATFORM updates currentPlatform", s.mode.currentPlatform === "youtube");

// ---- 2. SWITCH_PLATFORM 同值 → 不 reset ----
let s2 = createInitialState();
s2.features.swot = { status: "ready", requestId: "r1", data: { foo: 1 }, error: null };
s2.mode.currentPlatform = "google";
s2 = reduceAppState(s2, { type: "SWITCH_PLATFORM", platform: "google" });
t("SWITCH_PLATFORM same value does NOT reset swot", s2.features.swot.status === "ready");

// ---- 3. SWITCH_YT_ROLE 真的改變 → reset ----
let s3 = createInitialState();
s3.features.marketing = { status: "ready", requestId: "m1", data: { x: 1 }, error: null };
s3.mode.ytRoleSelection = "creator";
s3 = reduceAppState(s3, { type: "SWITCH_YT_ROLE", ytRole: "shop" });
t("SWITCH_YT_ROLE (creator→shop) resets marketing", s3.features.marketing.status === "idle");
t("SWITCH_YT_ROLE updates ytRoleSelection", s3.mode.ytRoleSelection === "shop");

// ---- 4. SWITCH_YT_ROLE 同值 → 不 reset ----
let s4 = createInitialState();
s4.features.marketing = { status: "ready", requestId: "m1", data: { x: 1 }, error: null };
s4.mode.ytRoleSelection = "creator";
s4 = reduceAppState(s4, { type: "SWITCH_YT_ROLE", ytRole: "creator" });
t("SWITCH_YT_ROLE same value does NOT reset marketing", s4.features.marketing.status === "ready");

// ---- 5. FETCH_ANALYZE_START 設 analyze=loading + reset 下游 ----
let s5 = createInitialState();
s5.features.swot = { status: "ready", requestId: "rOld", data: { x: 1 }, error: null };
s5.features.analyze = { status: "ready", requestId: "aOld", data: { y: 2 }, error: null };
s5 = reduceAppState(s5, { type: "FETCH_ANALYZE_START", requestId: "aNew" });
t("FETCH_ANALYZE_START → analyze.status=loading", s5.features.analyze.status === "loading");
t("FETCH_ANALYZE_START → analyze.requestId=aNew", s5.features.analyze.requestId === "aNew");
t("FETCH_ANALYZE_START → swot reset to idle", s5.features.swot.status === "idle");

// ---- 6. FETCH_ANALYZE_SUCCEEDED 不被 stale check 丟掉（接 START 之後）----
s5 = reduceAppState(s5, { type: "FETCH_ANALYZE_SUCCEEDED", requestId: "aNew", data: { newData: true } });
t("FETCH_ANALYZE_SUCCEEDED matches → analyze.status=ready", s5.features.analyze.status === "ready");
t("FETCH_ANALYZE_SUCCEEDED writes new data", s5.features.analyze.data?.newData === true);

// ---- 7. STREAM_START + STREAM_RESULT 完整路徑 ----
let s7 = createInitialState();
s7.features.swot = { status: "ready", requestId: "old", data: { z: 9 }, error: null };
s7 = reduceAppState(s7, { type: "STREAM_START", runId: "rid1", requestId: "aReq1" });
t("STREAM_START → swot reset", s7.features.swot.status === "idle");
t("STREAM_START → analyze.status=loading", s7.features.analyze.status === "loading");
s7 = reduceAppState(s7, { type: "STREAM_RESULT", runId: "rid1", requestId: "aReq1", data: { result: 1 } });
t("STREAM_RESULT → analyze.status=ready", s7.features.analyze.status === "ready");

// ---- 8. STREAM_CONNECTION_LOST 帶 requestId → 進 failed（P3.10-3-R3 regression）----
// adapters.js 必須帶 requestId，否則 reducer 的 stale check (prev.requestId !== action.requestId)
// 會把 action 丟掉，features.analyze 卡在 loading 永遠不 failed。
let s8 = createInitialState();
s8 = reduceAppState(s8, { type: "STREAM_START", runId: "rid8", requestId: "aReq8" });
t("STREAM_START (case 8) → analyze.status=loading", s8.features.analyze.status === "loading");
s8 = reduceAppState(s8, {
  type: "STREAM_CONNECTION_LOST",
  runId: "rid8",
  requestId: "aReq8",
  error: { kind: "connection_lost", message: "EventSource closed" },
});
t("STREAM_CONNECTION_LOST with matching requestId → analyze.status=failed", s8.features.analyze.status === "failed");
t("STREAM_CONNECTION_LOST writes error.kind", s8.features.analyze.error?.kind === "connection_lost");

// ---- 9. STREAM_CONNECTION_LOST 不帶 requestId → split state（stream.phase=failed、features.analyze 卡 loading）
// Codex round-3 補強：單純斷言 analyze 卡 loading 不夠，必須同時 assert stream.phase 進 failed，
// 才能暴露「adapter 漏帶 requestId 會產生 split state」這個 UX bug。case 8 修法正確，case 9 是 regression 保險。
let s9 = createInitialState();
s9 = reduceAppState(s9, { type: "STREAM_START", runId: "rid9", requestId: "aReq9" });
s9 = reduceAppState(s9, {
  type: "STREAM_CONNECTION_LOST",
  runId: "rid9",
  // intentionally no requestId — simulates pre-fix bug shape
  error: { kind: "connection_lost", message: "no requestId" },
});
t(
  "STREAM_CONNECTION_LOST without requestId → analyze stuck in loading (proves stale check active)",
  s9.features.analyze.status === "loading"
);
t(
  "STREAM_CONNECTION_LOST without requestId → stream.phase=failed (split state exposed)",
  s9.stream.phase === "failed"
);
t(
  "STREAM_CONNECTION_LOST without requestId → stream.error written",
  s9.stream.error?.kind === "connection_lost"
);

// ---- 10. STREAM_FAILED 帶 requestId → 進 failed ----
let s10 = createInitialState();
s10 = reduceAppState(s10, { type: "STREAM_START", runId: "rid10", requestId: "aReq10" });
s10 = reduceAppState(s10, {
  type: "STREAM_FAILED",
  runId: "rid10",
  requestId: "aReq10",
  error: { kind: "server_failed", message: "LLM timeout" },
});
t("STREAM_FAILED with matching requestId → analyze.status=failed", s10.features.analyze.status === "failed");

// ---- 11. runAnalyzeStream adapter 三條 terminal 路徑 dispatch shape（Codex round-4 補強）----
// 背景：
//   Round-3 的 case 11 只 assert STREAM_START 帶 requestId，但「STREAM_CONNECTION_LOST
//   漏 requestId」才是 P3.10-3-R3 修過的真 regression point。如果有人把 adapters.js line 107
//   的 requestId 拿掉，round-3 的 case 11 仍會全綠。
//
// Round-4 修法：
//   stub EventSource 要能 capture instance + listener，測試手動觸發 onerror / failed / result，
//   然後 assert 對應的 STREAM_CONNECTION_LOST / STREAM_FAILED / STREAM_RESULT action 都帶
//   跟 STREAM_START 一致的 requestId + runId。這是真正把 adapter terminal action shape
//   鎖在測試裡。
import { runAnalyzeStream } from "../src/static/v2/core/adapters.js";

const esInstances = [];
class StubEventSource {
  constructor(url) {
    this.url = url;
    this.readyState = 0; // CONNECTING
    this.listeners = {};
    this.onerror = null;
    esInstances.push(this);
  }
  close() { this.readyState = 2; /* CLOSED */ }
  addEventListener(type, cb) {
    (this.listeners[type] = this.listeners[type] || []).push(cb);
  }
  removeEventListener(type, cb) {
    if (!this.listeners[type]) return;
    this.listeners[type] = this.listeners[type].filter((l) => l !== cb);
  }
  // test helpers
  _emit(type, dataObj) {
    (this.listeners[type] || []).forEach((cb) => cb({ data: JSON.stringify(dataObj) }));
  }
  // P3.11-R4 補：Round-4 ROUND-4-5 — malformed JSON 路徑要能直接餵字串給 listener
  _emitRaw(type, rawData) {
    (this.listeners[type] || []).forEach((cb) => cb({ data: rawData }));
  }
  _fireError() {
    this.readyState = 2; // CLOSED
    if (this.onerror) this.onerror({});
  }
}
StubEventSource.CONNECTING = 0;
StubEventSource.OPEN = 1;
StubEventSource.CLOSED = 2;
globalThis.EventSource = StubEventSource;

// ---- 11a: onerror（連線層錯誤）→ STREAM_CONNECTION_LOST ----
// 真回歸保護：此 case 一旦把 adapters.js:107 的 requestId 拿掉，11a 最後兩個 assertion 會紅。
const cap11a = [];
const handle11a = runAnalyzeStream({
  url: "https://www.google.com/maps?cid=11a",
  platform: "google",
  ytRole: null,
  dispatch: (a) => cap11a.push(a),
});
const start11a = cap11a.find((a) => a.type === "STREAM_START");
t("11a STREAM_START dispatched", !!start11a);
t("11a handle.runId === STREAM_START.runId", handle11a.runId === start11a?.runId);
t("11a handle.requestId === STREAM_START.requestId", handle11a.requestId === start11a?.requestId);
const es11a = esInstances[esInstances.length - 1];
es11a._fireError();
const cl11a = cap11a.find((a) => a.type === "STREAM_CONNECTION_LOST");
t("11a onerror → STREAM_CONNECTION_LOST dispatched", !!cl11a);
t("11a STREAM_CONNECTION_LOST carries runId === STREAM_START.runId",
  cl11a?.runId === start11a?.runId && typeof cl11a?.runId === "string");
t("11a STREAM_CONNECTION_LOST carries requestId === STREAM_START.requestId (真回歸點)",
  cl11a?.requestId === start11a?.requestId && typeof cl11a?.requestId === "string");
t("11a STREAM_CONNECTION_LOST carries error VM", !!cl11a?.error && typeof cl11a.error === "object");
// P3.11-R3 fix（Codex round-3 issue 3）：errorVM 內部 requestId 必須對齊 STREAM_START.requestId，
// 不可以塞 runId（語意錯）。原本 api.js 只收 runId 當 placeholder，導致 ErrorVM 診斷追蹤錯誤對象。
t("11a errorVM.requestId === STREAM_START.requestId (診斷語意對齊)",
  cl11a?.error?.requestId === start11a?.requestId && typeof cl11a?.error?.requestId === "string");

// ---- 11b: 'failed' SSE event → STREAM_FAILED ----
const cap11b = [];
runAnalyzeStream({
  url: "https://www.google.com/maps?cid=11b",
  platform: "google",
  dispatch: (a) => cap11b.push(a),
});
const start11b = cap11b.find((a) => a.type === "STREAM_START");
const es11b = esInstances[esInstances.length - 1];
es11b._emit("failed", { error: { kind: "server_failed", message: "LLM timeout" } });
const failed11b = cap11b.find((a) => a.type === "STREAM_FAILED");
t("11b 'failed' event → STREAM_FAILED dispatched", !!failed11b);
t("11b STREAM_FAILED carries runId === STREAM_START.runId",
  failed11b?.runId === start11b?.runId && typeof failed11b?.runId === "string");
t("11b STREAM_FAILED carries requestId === STREAM_START.requestId",
  failed11b?.requestId === start11b?.requestId && typeof failed11b?.requestId === "string");

// ---- 11c: 'result' SSE event → STREAM_RESULT ----
const cap11c = [];
runAnalyzeStream({
  url: "https://www.google.com/maps?cid=11c",
  platform: "google",
  dispatch: (a) => cap11c.push(a),
});
const start11c = cap11c.find((a) => a.type === "STREAM_START");
const es11c = esInstances[esInstances.length - 1];
es11c._emit("result", { platform: "google", effective_yt_role: null, durationMs: 1234, data: { ok: true } });
const result11c = cap11c.find((a) => a.type === "STREAM_RESULT");
t("11c 'result' event → STREAM_RESULT dispatched", !!result11c);
t("11c STREAM_RESULT carries runId === STREAM_START.runId",
  result11c?.runId === start11c?.runId && typeof result11c?.runId === "string");
t("11c STREAM_RESULT carries requestId === STREAM_START.requestId",
  result11c?.requestId === start11c?.requestId && typeof result11c?.requestId === "string");

// ---- 11d: malformed 'result' JSON → STREAM_CONNECTION_LOST（不可 silent close）----
// 背景（Codex round-4 ROUND-4-5）：
//   原本 api.js result/failed listener 先 terminalReceived=true 再 safeParse。
//   safeParse 失敗（payload 非法 JSON）時，既不 dispatch onResult 也不 dispatch
//   onFailed，terminalReceived 已真，onerror 也不會再 fire → features.analyze
//   永遠卡在 loading。Round-4 修成「parse 失敗走 onConnectionError 並 close」。
//   這個 regression 一旦有人把 safeParse 失敗分支刪掉就會抓到。
const cap11d = [];
runAnalyzeStream({
  url: "https://www.google.com/maps?cid=11d",
  platform: "google",
  dispatch: (a) => cap11d.push(a),
});
const start11d = cap11d.find((a) => a.type === "STREAM_START");
const es11d = esInstances[esInstances.length - 1];
es11d._emitRaw("result", "NOT_JSON{{");
const cl11d = cap11d.find((a) => a.type === "STREAM_CONNECTION_LOST");
t("11d malformed result JSON → STREAM_CONNECTION_LOST dispatched (不 silent close)", !!cl11d);
t("11d STREAM_CONNECTION_LOST carries requestId === STREAM_START.requestId",
  cl11d?.requestId === start11d?.requestId && typeof cl11d?.requestId === "string");
// Round-5 ROUND-5-3：再鎖一層 — errorVM.requestId 也必須對齊 STREAM_START.requestId。
// 為什麼不夠：上一條只 assert action 外層 requestId（adapter 自己塞的），api.js 內部
// `Err.network(..., requestId ?? null)` 如果有人改成 `?? runId` 或 `null`，外層仍綠
// 內層卻變錯。errorVM 才是 UI 真正讀的診斷對象。
t("11d errorVM.requestId === STREAM_START.requestId（鎖 api.js malformed 分支內 Err.network 的 requestId）",
  cl11d?.error?.requestId === start11d?.requestId && typeof cl11d?.error?.requestId === "string");
t("11d errorVM message 指明 malformed",
  typeof cl11d?.error?.message === "string" && cl11d.error.message.toLowerCase().includes("malformed"));
// 11d 要求：後續 onerror fire 不再 double-dispatch（terminalReceived 已真）
es11d._fireError();
const conns11d = cap11d.filter((a) => a.type === "STREAM_CONNECTION_LOST");
t("11d malformed 後即使 onerror 再觸發，只 dispatch 一次 STREAM_CONNECTION_LOST", conns11d.length === 1);

// ---- 11e: malformed 'failed' JSON → STREAM_CONNECTION_LOST ----
const cap11e = [];
runAnalyzeStream({
  url: "https://www.google.com/maps?cid=11e",
  platform: "google",
  dispatch: (a) => cap11e.push(a),
});
const start11e = cap11e.find((a) => a.type === "STREAM_START");
const es11e = esInstances[esInstances.length - 1];
es11e._emitRaw("failed", "<<<broken>>>");
const cl11e = cap11e.find((a) => a.type === "STREAM_CONNECTION_LOST");
t("11e malformed failed JSON → STREAM_CONNECTION_LOST dispatched", !!cl11e);
t("11e STREAM_CONNECTION_LOST carries requestId === STREAM_START.requestId",
  cl11e?.requestId === start11e?.requestId && typeof cl11e?.requestId === "string");
t("11e errorVM.requestId === STREAM_START.requestId（鎖 api.js malformed failed 分支內 Err.network 的 requestId）",
  cl11e?.error?.requestId === start11e?.requestId && typeof cl11e?.error?.requestId === "string");
t("11e errorVM message 指明 malformed",
  typeof cl11e?.error?.message === "string" && cl11e.error.message.toLowerCase().includes("malformed"));

// ---- 11f: openSSE 沒帶 opts.requestId → errorVM.requestId === null（絕不可是 runId） ----
// Round-4 ROUND-4-4：原本 api.js 用 `requestId ?? runId` fallback，讓呼叫端誤以為 ErrorVM
// 有 requestId（實際是 runId）。改成 `requestId ?? null` 後，直接呼叫 openSSE 不給
// opts.requestId 時，errorVM.requestId 必須是 null，不可是 runId。
import { openSSE } from "../src/static/v2/core/api.js";
const cap11f = [];
openSSE(
  "/api/v4/analyze-stream?url=x",
  {
    onProgress: () => {},
    onResult: () => {},
    onFailed: () => {},
    onConnectionError: (err) => cap11f.push(err),
  },
  { runId: "run-should-not-leak" } // 故意只帶 runId，不帶 requestId
);
const es11f = esInstances[esInstances.length - 1];
es11f._fireError();
const err11f = cap11f[0];
t("11f openSSE 無 opts.requestId → onConnectionError 觸發", !!err11f);
t("11f errorVM.requestId === null（絕不 fallback 成 runId）", err11f?.requestId === null);
t("11f errorVM.requestId !== 'run-should-not-leak'（確認 runId 不會洩進 ErrorVM）",
  err11f?.requestId !== "run-should-not-leak");

console.log("\n--- Result:", pass, "pass /", fail, "fail ---");
process.exit(fail > 0 ? 1 : 0);
