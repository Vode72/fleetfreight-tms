import type { ParseKeys } from "i18next";

import type { IconName } from "./Icon";

export interface NavItem {
  /** Route path. */
  path: string;
  labelKey: ParseKeys;
  icon: IconName;
}

export interface NavSection {
  id: string;
  labelKey: ParseKeys;
  items: readonly NavItem[];
}

export const DASHBOARD_ITEM: NavItem = { path: "/", labelKey: "nav.dashboard", icon: "dashboard" };

export const NAV_SECTIONS: readonly NavSection[] = [
  {
    id: "load-planning",
    labelKey: "nav.sections.loadPlanning",
    items: [
      { path: "/orders", labelKey: "nav.items.orders", icon: "orders" },
      { path: "/trips", labelKey: "nav.items.trips", icon: "trips" },
      { path: "/customers", labelKey: "nav.items.customers", icon: "customers" },
    ],
  },
  {
    id: "traffic-planning",
    labelKey: "nav.sections.trafficPlanning",
    items: [
      { path: "/board", labelKey: "nav.items.board", icon: "board" },
      { path: "/job-workspace", labelKey: "nav.items.jobWorkspace", icon: "job" },
      { path: "/fleet-timeline", labelKey: "nav.items.fleetTimeline", icon: "timeline" },
      { path: "/route-risk", labelKey: "nav.items.routeRisk", icon: "route" },
    ],
  },
  {
    id: "administration",
    labelKey: "nav.sections.administration",
    items: [
      { path: "/fleet-partners", labelKey: "nav.items.fleetPartners", icon: "fleet" },
      { path: "/pricing", labelKey: "nav.items.pricing", icon: "pricing" },
      { path: "/settings", labelKey: "nav.items.settings", icon: "settings" },
    ],
  },
];
