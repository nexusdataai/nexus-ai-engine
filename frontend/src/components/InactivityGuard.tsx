import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useSyncExternalStore } from "react";

import { useInactivityLogout } from "@/hooks/useInactivityLogout";
import { authStore } from "@/services/authStore";

/** Signs out and reloads when the session is idle too long. */
export function InactivityGuard() {
  const user = useSyncExternalStore(authStore.subscribe, authStore.get, () => null);
  const queryClient = useQueryClient();

  const handleTimeout = useCallback(() => {
    authStore.clear();
    queryClient.clear();
    const cognitoUrl = authStore.cognitoLoginUrl();
    window.location.replace(cognitoUrl || "/");
  }, [queryClient]);

  useInactivityLogout({
    enabled: Boolean(user),
    onTimeout: handleTimeout,
  });

  return null;
}
