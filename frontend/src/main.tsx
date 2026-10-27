import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { AppStateProvider } from "./appstate";
import { I18nProvider } from "./i18n";
import { JobsProvider } from "./jobs";
import { LanGate } from "./components/LanAccess";
import { MetaProvider } from "./meta";
import { ToastProvider } from "./toast";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <I18nProvider>
      <LanGate>
        <MetaProvider>
          <ToastProvider>
            <JobsProvider>
              <AppStateProvider>
                <App />
              </AppStateProvider>
            </JobsProvider>
          </ToastProvider>
        </MetaProvider>
      </LanGate>
    </I18nProvider>
  </StrictMode>,
);
