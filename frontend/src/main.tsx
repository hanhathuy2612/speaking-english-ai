import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
// Shared styles first: page stylesheets (imported by the pages below) must come later in the
// bundle so that their rules win over base rules of the same specificity.
import "./styles/base.css";
import { BenchPage } from "./features/bench/BenchPage";
import { CheckPage } from "./features/check/CheckPage";
import { FluencyPage } from "./features/fluency/FluencyPage";
import { HistoryPage } from "./features/history/HistoryPage";
import { LessonPage } from "./features/lesson/LessonPage";
import { PracticePage } from "./features/practice/PracticePage";
import { ReviewPage } from "./features/review/ReviewPage";
import { RoadmapPage } from "./features/roadmap/RoadmapPage";
import { SoundsPage } from "./features/sounds/SoundsPage";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<PracticePage />} />
        <Route path="/review" element={<ReviewPage />} />
        <Route path="/roadmap" element={<RoadmapPage />} />
        <Route path="/sounds" element={<SoundsPage />} />
        <Route path="/fluency" element={<FluencyPage />} />
        <Route path="/check" element={<CheckPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/bench" element={<BenchPage />} />
        <Route path="/lesson/:unitId" element={<LessonPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
