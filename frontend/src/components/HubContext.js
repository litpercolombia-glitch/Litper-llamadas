import { createContext, useContext } from "react";

// When a page renders inside a hub (a tabbed parent), we set this flag so the
// page's own <Layout/> renders bare — no duplicated Sidebar/Header/etc.
export const HubContext = createContext(false);
export function useInHub() { return useContext(HubContext); }
