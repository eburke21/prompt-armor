import { Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { Compare } from "./pages/Compare";
import { Dashboard } from "./pages/Dashboard";
import { Report } from "./pages/Report";
import { RunResults } from "./pages/RunResults";
import { Sandbox } from "./pages/Sandbox";
import { TaxonomyBrowser } from "./pages/TaxonomyBrowser";
import { TechniqueDetail } from "./pages/TechniqueDetail";

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/taxonomy" element={<TaxonomyBrowser />} />
        <Route path="/taxonomy/:technique" element={<TechniqueDetail />} />
        <Route path="/sandbox" element={<Sandbox />} />
        <Route path="/sandbox/:runId" element={<RunResults />} />
        <Route path="/compare" element={<Compare />} />
        <Route path="/report/:runId" element={<Report />} />
      </Route>
    </Routes>
  );
}
