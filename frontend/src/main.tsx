import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
// Shared styles first: page stylesheets (imported by the pages below) must come later in the
// bundle so that their rules win over base rules of the same specificity.
import "./styles/base.css";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { GuestOnly, RequireAdmin, RequireAuth } from "./auth/guards";
import { AccountPage } from "./features/account/AccountPage";
import { ContentPage } from "./features/admin/ContentPage";
import { UnitEditor } from "./features/admin/UnitEditor";
import { UsersPage } from "./features/admin/UsersPage";
import { ForgotPage, ResetPage, SignupPage, VerifyPage } from "./features/auth/EmailPages";
import { LoginPage } from "./features/auth/LoginPage";
import { BenchPage } from "./features/bench/BenchPage";
import { CheckPage } from "./features/check/CheckPage";
import { FluencyPage } from "./features/fluency/FluencyPage";
import { HistoryPage } from "./features/history/HistoryPage";
import { LessonPage } from "./features/lesson/LessonPage";
import { PracticePage } from "./features/practice/PracticePage";
import { ReviewPage } from "./features/review/ReviewPage";
import { RoadmapPage } from "./features/roadmap/RoadmapPage";
import { SoundsPage } from "./features/sounds/SoundsPage";
import { TalkPracticePage } from "./features/talk/TalkPracticePage";

/** One route tree, three gates (auth/guards.tsx): guests only, logged in, admin. The server checks the
 * login and the role again on every API call, so these gates decide what is shown, not what is allowed. */
function AppRoutes() {
  const { user } = useAuth();
  if (user === undefined) return null; // asking the server who is logged in, a few milliseconds
  return (
    <Routes>
      <Route element={<GuestOnly />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/forgot" element={<ForgotPage />} />
      </Route>
      {/* Email links work logged in or not. */}
      <Route path="/verify" element={<VerifyPage />} />
      <Route path="/reset" element={<ResetPage />} />
      <Route element={<RequireAuth />}>
        <Route path="/" element={<PracticePage />} />
        <Route path="/review" element={<ReviewPage />} />
        <Route path="/roadmap" element={<RoadmapPage />} />
        <Route path="/sounds" element={<SoundsPage />} />
        <Route path="/fluency" element={<FluencyPage />} />
        <Route path="/check" element={<CheckPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/lesson/:unitId" element={<LessonPage />} />
        <Route path="/talk/:talkId" element={<LessonPage />} />
        <Route path="/talk/:talkId/practice" element={<TalkPracticePage />} />
        <Route path="/account" element={<AccountPage />} />
        <Route element={<RequireAdmin />}>
          <Route path="/bench" element={<BenchPage />} />
          <Route path="/admin" element={<Navigate to="/admin/users" replace />} />
          <Route path="/admin/users" element={<UsersPage />} />
          <Route path="/admin/content" element={<ContentPage />} />
          <Route path="/admin/units/:unitId" element={<UnitEditor />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
