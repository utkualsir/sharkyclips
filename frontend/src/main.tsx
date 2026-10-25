import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { AppStateProvider } from "./appstate";
import { I18nProvider } from "./i18n";
import { JobsProvider } from "./jobs";
import { MetaProvider } from "./meta";
import { ToastProvider } from "./toast";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <I18nProvider>
      <MetaProvider>
        <ToastProvider>
          <JobsProvider>
            <AppStateProvider>
              <App />
            </AppStateProvider>
          </JobsProvider>
        </ToastProvider>
      </MetaProvider>
    </I18nProvider>
  </StrictMode>,
);
