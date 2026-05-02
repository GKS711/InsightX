import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { DashboardPage } from "./pages/DashboardPage";
import { StoreDetailPage } from "./pages/StoreDetailPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="/stores/:id" element={<StoreDetailPage />} />
        <Route path="/stores" element={<DashboardPage />} />
        <Route path="/reports" element={<ReportsPlaceholder />} />
      </Route>
    </Routes>
  );
}

function ReportsPlaceholder() {
  return (
    <div className="space-y-4">
      <h1 className="display-lg">Reports</h1>
      <p className="text-ink-muted">PDF / DOCX 報表（v5.0.0-alpha 後續加入）</p>
    </div>
  );
}
