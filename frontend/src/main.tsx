import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { BenchPage } from "./features/bench/BenchPage";
import { HistoryPage } from "./features/history/HistoryPage";
import { PracticePage } from "./features/practice/PracticePage";
import "./styles/base.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<PracticePage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/bench" element={<BenchPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
