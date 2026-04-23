const fs = require("fs");
const path = require("path");
const parser = require("@babel/parser");
// 改用 __dirname 相對路徑，避免硬編碼任何 sandbox / session 路徑（Codex P3.9-7 review fix）
const targetPath = path.resolve(__dirname, "src/static/v2/index.html");
const html = fs.readFileSync(targetPath, "utf8");
const m = html.match(/<script type="text\/babel" data-presets="react">([\s\S]*?)<\/script>/);
if (!m) { console.error("no babel block"); process.exit(1); }
const code = m[1];
const lines = code.split("\n").length;
try {
  parser.parse(code, { sourceType: "module", plugins: ["jsx"] });
  console.log("OK · lines:", lines);
} catch (e) {
  console.error("PARSE ERROR:", e.message);
  const line = e.loc && e.loc.line;
  if (line) {
    const all = code.split("\n");
    for (let i = Math.max(0, line - 3); i < Math.min(all.length, line + 2); i++) {
      console.error((i + 1) + ": " + all[i]);
    }
  }
  process.exit(1);
}
