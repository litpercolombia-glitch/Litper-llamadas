import { createContext, useContext } from "react";

// When a page renders inside a hub (a tabbed parent), we set this flag so the
// page's own <Layout/> renders bare — no duplicated Sidebar/Header/etc.
// The value is the help key of the active tab (see constants/help.js TAB_HELP),
// so the embedded Layout can paint that tab's instructions automatically.
export const HubContext = createContext(false);
export function useInHub() { return useContext(HubContext); }
