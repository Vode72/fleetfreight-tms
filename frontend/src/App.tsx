import { Route, Routes } from "react-router";

import { AuthProvider } from "./auth/AuthProvider";
import { RequireAuth } from "./auth/RequireAuth";
import { RequireRole } from "./auth/RequireRole";
import { AppLayout } from "./layout/AppLayout";
import { NAV_SECTIONS } from "./layout/navigation";
import { DashboardPage } from "./pages/DashboardPage";
import { ForbiddenPage } from "./pages/ForbiddenPage";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";

/** Routes only. The router itself is provided by main.tsx (or by tests). `/login` is the only public route. */
export function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<RequireAuth />}>
          <Route element={<AppLayout />}>
            <Route index element={<DashboardPage />} />
            {NAV_SECTIONS.flatMap((section) => section.items.map((item) => ({ item, roles: section.roles }))).map(
              ({ item, roles }) => {
                const page = <PlaceholderPage titleKey={item.labelKey} />;
                return (
                  <Route
                    key={item.path}
                    path={item.path}
                    element={
                      roles ? (
                        <RequireRole roles={roles} fallback={<ForbiddenPage />}>
                          {page}
                        </RequireRole>
                      ) : (
                        page
                      )
                    }
                  />
                );
              },
            )}
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Route>
      </Routes>
    </AuthProvider>
  );
}
