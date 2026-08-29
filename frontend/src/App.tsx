import { Route, Routes } from "react-router-dom";

import Layout from "@/components/Layout";
import { AuthCallbackPage } from "@/pages/AuthCallbackPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { ExecutionDetailPage } from "@/pages/ExecutionDetailPage";
import { ExecutionsListPage } from "@/pages/ExecutionsListPage";
import { JourneyDetailPage } from "@/pages/JourneyDetailPage";
import { JourneyStudioPage } from "@/pages/JourneyStudioPage";
import { JourneysListPage } from "@/pages/JourneysListPage";
import { SchedulesPage } from "@/pages/SchedulesPage";
import { StageJobDetailPage } from "@/pages/StageJobDetailPage";
import { ToolsCatalogPage } from "@/pages/ToolsCatalogPage";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route index element={<DashboardPage />} />
        <Route path="journeys" element={<JourneysListPage />} />
        <Route path="journeys/:journeyId/studio" element={<JourneyStudioPage />} />
        <Route path="journeys/:journeyId" element={<JourneyDetailPage />} />
        <Route path="executions" element={<ExecutionsListPage />} />
        <Route path="executions/stage/:journeyId/:jobId" element={<StageJobDetailPage />} />
        <Route path="executions/:executionId" element={<ExecutionDetailPage />} />
        <Route path="schedules" element={<SchedulesPage />} />
        <Route path="tools" element={<ToolsCatalogPage />} />
        <Route path="auth/callback" element={<AuthCallbackPage />} />
      </Routes>
    </Layout>
  );
}
