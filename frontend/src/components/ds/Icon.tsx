/**
 * Product icon.
 * ----------------------------------------------------------------------------
 * One icon family for every Nexus AI product: UIcons regular rounded by
 * Freepik (the family published on Magnific / Flaticon stock). The compiled
 * set in `icons.generated.ts` is shared with the Nexus AI ontology product.
 * Licence: Flaticon licence (active Freepik/Magnific subscription or a
 * visible credit to Flaticon).
 *
 * Usage: <Icon name="database" className="h-4 w-4" />
 * Icons inherit the text colour (currentColor) and default to 16px.
 */
import * as React from "react";
import { HelpCircle } from "lucide-react";

import { cn } from "@/lib/utils";
import { ICONS } from "./icons.generated";

export type IconName =
  | "activity" | "alert-triangle" | "apps" | "arrow-right" | "arrow-up-right" | "bell" | "bolt"
  | "bot" | "box" | "brain-ai" | "calendar" | "chart-bar" | "check-circle" | "check"
  | "chevron-down" | "chevron-left" | "chevron-right" | "chevron-up" | "chevrons-left"
  | "chevrons-right" | "clipboard" | "clock" | "close" | "cloud" | "code" | "copy"
  | "cross-circle" | "cube" | "dashboard" | "database" | "document" | "download" | "edit"
  | "expand" | "external-link" | "eye" | "file-code" | "filter" | "flask" | "folder" | "globe"
  | "graph" | "grid" | "heartbeat" | "help" | "history" | "home" | "info" | "key" | "layers"
  | "link" | "list" | "lock" | "logout" | "menu" | "minus" | "moon" | "more" | "network"
  | "pause" | "play" | "plug" | "plus" | "refresh" | "route" | "search" | "send" | "server"
  | "settings" | "shield-check" | "shuffle" | "sliders" | "sparkles" | "spinner" | "star"
  | "stethoscope" | "sun" | "table" | "target" | "terminal" | "trash" | "trend-up" | "upload"
  | "user" | "users" | "workflow" | "wrench"
  | (string & {});

interface IconProps extends Omit<React.SVGAttributes<SVGSVGElement>, "name"> {
  name: IconName;
  /** Accessible label. Omit for decorative icons next to text. */
  label?: string;
}

export function Icon({ name, label, className, ...rest }: IconProps) {
  const a11y = label ? { role: "img", "aria-label": label } : { "aria-hidden": true };
  const def = (ICONS as Record<string, { viewBox: string; body: string }>)[name];

  if (def) {
    return (
      <svg
        viewBox={def.viewBox}
        fill="currentColor"
        focusable="false"
        className={cn("h-4 w-4 shrink-0", className)}
        {...a11y}
        {...rest}
        dangerouslySetInnerHTML={{ __html: def.body }}
      />
    );
  }

  return <HelpCircle className={cn("h-4 w-4 shrink-0", className)} strokeWidth={1.6} {...(a11y as object)} />;
}

export default Icon;
