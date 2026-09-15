"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { STORAGE_KEYS } from "./constants";

/** Redirect to /login when there is no session and tell the page when it may fetch data.
 *
 * Every page that loads data on mount must use this hook (instead of assuming AdminShell
 * already validated the session), so it never fires a request without a token that ends
 * in a 401 and an unnecessary full reload.
 */
export function useAuthReady(): boolean {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem(STORAGE_KEYS.token)) router.replace("/login");
    else setReady(true);
  }, [router]);

  return ready;
}

export function clearSession(): void {
  localStorage.removeItem(STORAGE_KEYS.token);
  localStorage.removeItem(STORAGE_KEYS.user);
  localStorage.removeItem(STORAGE_KEYS.role);
}
