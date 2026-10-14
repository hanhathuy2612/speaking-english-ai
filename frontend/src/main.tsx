import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useSearchParams } from "react-router";
// Shared styles first: page stylesheets (imported by the pages below) must come later in the
// bundle so that their rules win over base rules of the same specificity.
import "./styles/base.css";
import { watchExpiredLogin } from "./api/http";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { AccountPage } from "./features/account/AccountPage";
import { ContentPage } from "./features/admin/ContentPage";
import { UnitEditor } from "./features/admin/UnitEditor";
import { UsersPage } from "./features/admin/UsersPage";
import { ForgotPage, ResetPage, SignupPage, VerifyPage } from "./features/auth/EmailPages";
import { LoginPage, nextPath } from "./features/auth/LoginPage";
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

watchExpiredLogin();

/** Logged out: only the login and email pages; any other address comes back here after login. */
function ToLogin() {
  const { pathname, search } = useLocation();
  return <Navigate to={`/login?next=${encodeURIComponent(pathname + search)}`} replace />;
}

function AfterLogin() {
  const [params] = useSearchParams();
  return <Navigate to={nextPath(params)} replace />;
}

function AppRoutes() {
  const { user } = useAuth();
  if (user === undefined) return null; // asking the server who is logged in, a few milliseconds
  const email = (
    <>
      <Route path="/verify" element={<VerifyPage />} />
      <Route path="/reset" element={<ResetPage />} />
    </>
  );
  if (!user)
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/forgot" element={<ForgotPage />} />
        {email}
        <Route path="*" element={<ToLogin />} />
      </Routes>
    );
  const admin = user.role === "admin";
  return (
    <Routes>
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
      {email}
      {admin && <Route path="/bench" element={<BenchPage />} />}
      {admin && <Route path="/admin" element={<Navigate to="/admin/users" replace />} />}
      {admin && <Route path="/admin/users" element={<UsersPage />} />}
      {admin && <Route path="/admin/content" element={<ContentPage />} />}
      {admin && <Route path="/admin/units/:unitId" element={<UnitEditor />} />}
      <Route path="/login" element={<AfterLogin />} />
      <Route path="/signup" element={<AfterLogin />} />
      <Route path="*" element={<Navigate to="/" replace />} />
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
