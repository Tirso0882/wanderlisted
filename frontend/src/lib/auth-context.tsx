"use client";

import { createContext, useContext, type ReactNode } from "react";
import { useClerk, useUser, UserButton } from "@clerk/nextjs";

type AuthContextValue = {
  enabled: boolean;
  isLoaded: boolean;
  isSignedIn: boolean;
  openSignIn: () => void;
};

const guestAuth: AuthContextValue = {
  enabled: false,
  isLoaded: true,
  isSignedIn: false,
  openSignIn: () => {},
};

const AuthContext = createContext<AuthContextValue>(guestAuth);

function ClerkAuthBridge({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn } = useUser();
  const clerk = useClerk();
  return (
    <AuthContext.Provider
      value={{
        enabled: true,
        isLoaded,
        isSignedIn: Boolean(isSignedIn),
        openSignIn: () => clerk.openSignIn({}),
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function AuthBridge({
  enabled,
  children,
}: {
  enabled: boolean;
  children: ReactNode;
}) {
  if (!enabled) {
    return <AuthContext.Provider value={guestAuth}>{children}</AuthContext.Provider>;
  }
  return <ClerkAuthBridge>{children}</ClerkAuthBridge>;
}

export function useAuthState() {
  return useContext(AuthContext);
}

export function EmbeddedAccountButton({ label }: { label: string }) {
  const auth = useAuthState();
  if (!auth.enabled || !auth.isSignedIn) return null;
  return (
    <div aria-label={label}>
      <UserButton userProfileMode="modal" />
    </div>
  );
}
