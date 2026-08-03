import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

type SidebarChrome = {
  mobileOpen: boolean;
  setMobileOpen: (open: boolean) => void;
  mini: boolean;
  setMini: (mini: boolean) => void;
};

const SidebarChromeContext = createContext<SidebarChrome | null>(null);

export function SidebarChromeProvider({ children }: { children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [mini, setMini] = useState(false);
  const value = useMemo(
    () => ({ mobileOpen, setMobileOpen, mini, setMini }),
    [mobileOpen, mini],
  );
  return <SidebarChromeContext.Provider value={value}>{children}</SidebarChromeContext.Provider>;
}

export function useSidebarChrome() {
  const ctx = useContext(SidebarChromeContext);
  if (!ctx) throw new Error("useSidebarChrome requires SidebarChromeProvider");
  return ctx;
}
