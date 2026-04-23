/**
 * InsightX v4 · Bootstrap bridge
 *
 * 目的：把 ES module 的 core/ + hooks/ 橋接到 Babel-standalone 的 window 全域環境。
 *
 * 載入時機：
 *   <script type="module" src="/bootstrap.js"></script>  放在 <script type="text/babel"> 前面
 *   瀏覽器規格：type="module" 等同 defer。Babel standalone 自己 hook DOMContentLoaded
 *   才掃 text/babel 區塊，所以這支一定在 Babel 執行 component body 前跑完。
 *
 * 給 Babel 區塊消費（自己 destructure）：
 *   const { useAppReducer, useAnalyzeStream, useLocalStorage,
 *           Adapters, Async, Err, createInitialState, reduceAppState } = window.IX;
 */

import { Async, Err, isFresh, formatErrorMessage } from "./core/async.js";
import { Adapters, runAnalyzeStream } from "./core/adapters.js";
import { apiFetch, openSSE } from "./core/api.js";
import { nextRequestId, nextRunId } from "./core/ids.js";

import { useLocalStorage, readFromStorage, writeToStorage } from "./hooks/useLocalStorage.js";
import {
  useAppReducer,
  createInitialState,
  reduceAppState,
  hydrateInitialState,
} from "./hooks/useAppReducer.js";
import { useAnalyzeStream } from "./hooks/useAnalyzeStream.js";

const IX = Object.freeze({
  // 版本
  version: "4.0.0",

  // core/
  Async,
  Err,
  isFresh,
  formatErrorMessage,
  Adapters,
  runAnalyzeStream,
  apiFetch,
  openSSE,
  nextRequestId,
  nextRunId,

  // hooks/
  useLocalStorage,
  useAppReducer,
  useAnalyzeStream,

  // reducer primitives（測試 / devtools 用）
  createInitialState,
  reduceAppState,
  hydrateInitialState,

  // storage primitives（reducer 外部如果要直接讀/寫某個 key 用）
  readFromStorage,
  writeToStorage,
});

window.IX = IX;
window.dispatchEvent(new CustomEvent("ix:ready", { detail: { version: IX.version } }));

// 方便 console debug
if (window && !window.__IX_SILENT__) {
  console.info(`[IX] bootstrap ready · v${IX.version}`);
}
