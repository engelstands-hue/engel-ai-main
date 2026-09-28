import { Route, Routes } from "react-router-dom";
import { SiteShell } from "./components/SiteShell";
import { placeholders } from "./data/site";
import { AboutPage } from "./pages/AboutPage";
import { ArchiveEditionsPage } from "./pages/ArchiveEditionsPage";
import { AgentsPage } from "./pages/AgentsPage";
import { AppsPage } from "./pages/AppsPage";
import { CommunityPage } from "./pages/CommunityPage";
import { DocsPage } from "./pages/DocsPage";
import { EngelMainPage } from "./pages/EngelMainPage";
import { GenesisPage } from "./pages/GenesisPage";
import { HomePage } from "./pages/HomePage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";
import { PlatformPage } from "./pages/PlatformPage";
import { ContactPage, PrivacyPage, SecurityPage, TermsPage } from "./pages/PublicInfoPages";
import { StatusPage } from "./pages/StatusPage";
import { TechnologyPage } from "./pages/TechnologyPage";

export default function App() {
  return (
    <SiteShell>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/engel-ai-main" element={<EngelMainPage />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="/technology" element={<TechnologyPage />} />
        <Route path="/platform" element={<PlatformPage />} />
        <Route path="/apps" element={<AppsPage />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/genesis" element={<GenesisPage />} />
        <Route path="/archive-editions" element={<ArchiveEditionsPage />} />
        <Route path="/community" element={<CommunityPage />} />
        <Route path="/docs" element={<DocsPage />} />
        <Route path="/status" element={<StatusPage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="/terms" element={<TermsPage />} />
        <Route path="/security" element={<SecurityPage />} />
        <Route path="/contact" element={<ContactPage />} />
        {placeholders.map((placeholder) => (
          <Route
            key={placeholder.path}
            path={placeholder.path}
            element={<PlaceholderPage placeholder={placeholder} />}
          />
        ))}
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </SiteShell>
  );
}
