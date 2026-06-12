// =============================================================================
// Scrum app — UI registrations
// =============================================================================
// The platform's Vite build discovers each apps/<id>/ui/index.js via
// import.meta.glob and merges the exported registrations into the runtime
// launcher.

import { lazy } from "react";
import { ClipboardList } from "lucide-react";

export default [
  {
    id: "scrum",
    name: "Scrum",
    icon: ClipboardList,
    component: lazy(() => import("./ScrumApp")),
    singleton: true,
  },
];
