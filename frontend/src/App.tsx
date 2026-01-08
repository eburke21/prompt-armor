import { Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { Dashboard } from "./pages/Dashboard";
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
      </Route>
    </Routes>
  );
}
