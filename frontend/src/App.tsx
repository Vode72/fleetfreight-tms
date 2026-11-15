import { Route, Routes } from "react-router";

import { AppLayout } from "./layout/AppLayout";
import { NAV_SECTIONS } from "./layout/navigation";
import { DashboardPage } from "./pages/DashboardPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";

/** Routes only. The router itself is provided by main.tsx (or by tests). */
export function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<DashboardPage />} />
        {NAV_SECTIONS.flatMap((section) => section.items).map((item) => (
          <Route key={item.path} path={item.path} element={<PlaceholderPage titleKey={item.labelKey} />} />
        ))}
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
