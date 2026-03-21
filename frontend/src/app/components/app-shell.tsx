"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { supabase } from "../../lib/supabase-browser";
import { resolveAvatarUrl } from "../../lib/avatar";

const appLinks = [
  { label: "Dashboard", href: "/app/dashboard" },
  { label: "Projects", href: "/app/projects" },
  { label: "Pipelines", href: "/app/pipelines" },
  { label: "Settings", href: "/app/settings" }
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const rootRef = useRef<HTMLDivElement | null>(null);
  const profileMenuRef = useRef<HTMLDivElement | null>(null);
  const profileDropdownRef = useRef<HTMLDivElement | null>(null);
  const profileButtonRef = useRef<HTMLButtonElement | null>(null);
  const apiBaseUrl = useMemo(
    () => process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000",
    []
  );
  const [displayName, setDisplayName] = useState("Workspace");
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false);
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
  const [isLogoutConfirmOpen, setIsLogoutConfirmOpen] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [profileMenuPosition, setProfileMenuPosition] = useState({ top: 88, right: 24 });
  const [isDomReady, setIsDomReady] = useState(false);
  const [isAuthChecked, setIsAuthChecked] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    let active: HTMLElement | null = null;
    const onMove = (event: MouseEvent) => {
      const rect = root.getBoundingClientRect();
      const x = ((event.clientX - rect.left) / rect.width) * 100;
      const y = ((event.clientY - rect.top) / rect.height) * 100;
      root.style.setProperty("--mx", `${x}%`);
      root.style.setProperty("--my", `${y}%`);

      const target = (event.target as HTMLElement | null)?.closest(".magnetic") as HTMLElement | null;
      if (active && active !== target) {
        active.style.setProperty("--tx", "0px");
        active.style.setProperty("--ty", "0px");
      }
      active = target;
      if (!target) return;
      const targetRect = target.getBoundingClientRect();
      const localX = ((event.clientX - targetRect.left) / targetRect.width) * 100;
      const localY = ((event.clientY - targetRect.top) / targetRect.height) * 100;
      target.style.setProperty("--mx", `${localX}%`);
      target.style.setProperty("--my", `${localY}%`);
      target.style.setProperty("--tx", `${(localX - 50) / 6}px`);
      target.style.setProperty("--ty", `${(localY - 50) / 6}px`);
    };
    const onClick = (event: MouseEvent) => {
      const target = (event.target as HTMLElement | null)?.closest(".ripple") as HTMLElement | null;
      if (!target) return;
      const rect = target.getBoundingClientRect();
      const ink = document.createElement("span");
      ink.className = "ripple-ink";
      ink.style.left = `${event.clientX - rect.left - 60}px`;
      ink.style.top = `${event.clientY - rect.top - 60}px`;
      target.appendChild(ink);
      window.setTimeout(() => ink.remove(), 700);
    };
    root.addEventListener("mousemove", onMove);
    root.addEventListener("click", onClick);
    return () => {
      root.removeEventListener("mousemove", onMove);
      root.removeEventListener("click", onClick);
    };
  }, []);

  useEffect(() => {
    setIsDomReady(true);
  }, []);

  useEffect(() => {
    const onDocumentClick = (event: MouseEvent) => {
      const target = event.target as Node | null;
      if (!target) return;
      const clickedInsideTrigger = profileMenuRef.current?.contains(target) ?? false;
      const clickedInsideDropdown = profileDropdownRef.current?.contains(target) ?? false;
      if (!clickedInsideTrigger && !clickedInsideDropdown) {
        setIsProfileMenuOpen(false);
      }
    };

    document.addEventListener("mousedown", onDocumentClick);
    return () => document.removeEventListener("mousedown", onDocumentClick);
  }, []);

  useEffect(() => {
    if (!isProfileMenuOpen) return;

    const updatePosition = () => {
      const rect = profileButtonRef.current?.getBoundingClientRect();
      if (!rect) return;
      setProfileMenuPosition({
        top: Math.round(rect.bottom + 8),
        right: Math.max(12, Math.round(window.innerWidth - rect.right)),
      });
    };

    updatePosition();
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [isProfileMenuOpen]);

  useEffect(() => {
    const loadProfile = async () => {
      try {
        const [{ data: userData }, { data: sessionData }] = await Promise.all([
          supabase.auth.getUser(),
          supabase.auth.getSession()
        ]);

        const user = userData.user;
        const token = sessionData.session?.access_token;

        if (user?.email) {
          setDisplayName(user.user_metadata?.full_name || user.email.split("@")[0] || user.email);
        }

        if (!token) return;

        const response = await fetch(`${apiBaseUrl}/profile/me`, {
          headers: {
            Authorization: `Bearer ${token}`
          }
        });

        if (!response.ok) return;
        const profile = await response.json();
        if (profile.username || profile.full_name || profile.email) {
          setDisplayName(profile.username || profile.full_name || profile.email);
        }
        if (profile.avatar_url) {
          setAvatarUrl(await resolveAvatarUrl(profile.avatar_url));
        }
      } catch {
        // Backend may be down during local dev; keep shell usable without crashing.
      }
    };

    loadProfile();
  }, [apiBaseUrl]);

  useEffect(() => {
    const checkAuth = async () => {
      const { data } = await supabase.auth.getSession();
      const session = data.session;
      setIsAuthenticated(!!session);
      setIsAuthChecked(true);
      if (!session) {
        router.replace("/auth");
      }
    };

    checkAuth();

    const { data: subscription } = supabase.auth.onAuthStateChange((event, session) => {
      const authenticated = !!session;
      setIsAuthenticated(authenticated);
      if (event === "SIGNED_OUT" || !authenticated) {
        router.replace("/auth");
      }
    });

    return () => {
      subscription.subscription.unsubscribe();
    };
  }, [router]);

  const initials = displayName
    .split(" ")
    .map((part) => part.trim()[0])
    .filter(Boolean)
    .join("")
    .slice(0, 2)
    .toUpperCase();

  const handleLogout = async () => {
    try {
      setIsLoggingOut(true);
      await supabase.auth.signOut();
      router.replace("/auth");
    } finally {
      setIsLoggingOut(false);
      setIsProfileMenuOpen(false);
      setIsMobileNavOpen(false);
      setIsLogoutConfirmOpen(false);
    }
  };

  const requestLogout = () => {
    setIsProfileMenuOpen(false);
    setIsMobileNavOpen(false);
    setIsLogoutConfirmOpen(true);
  };

  if (isAuthChecked && !isAuthenticated) {
    return null;
  }

  return (
    <div ref={rootRef} className="min-h-screen bg-bone cursor-reactive">
      <header className="relative z-40 border-b border-dune/15 bg-white/70">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-6">
          <Link href="/" className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-ink text-bone">B</div>
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-dune">Baxel</p>
              <p className="text-sm text-ink">{displayName}</p>
            </div>
          </Link>
          <nav className="hidden items-center gap-5 text-sm text-dune md:flex">
            {appLinks.map((link) => (
              <Link key={link.href} href={link.href} className="transition hover:text-ink">
                {link.label}
              </Link>
            ))}
          </nav>
          <div className="relative flex items-center gap-3 text-sm" ref={profileMenuRef}>
            <span className="rounded-full bg-mint/20 px-3 py-1 text-xs uppercase tracking-[0.2em] text-dune">
              Live
            </span>
            <button
              type="button"
              onClick={() => setIsMobileNavOpen((prev) => !prev)}
              className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-dune/20 bg-white/80 text-ink md:hidden"
              aria-label="Toggle navigation menu"
            >
              <span className="text-base">☰</span>
            </button>
            <button
              ref={profileButtonRef}
              type="button"
              onClick={() => setIsProfileMenuOpen((prev) => !prev)}
              className="flex items-center gap-2 rounded-full border border-dune/20 bg-white/80 px-2 py-1 transition hover:border-dune/40"
            >
              {avatarUrl ? (
                <img src={avatarUrl} alt="Profile" className="h-9 w-9 rounded-full object-cover" />
              ) : (
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-ink text-xs font-semibold text-bone">
                  {initials || "U"}
                </div>
              )}
              <span className="hidden max-w-36 truncate text-xs font-semibold text-ink sm:block">Profile</span>
              <span
                className={`hidden text-[10px] text-dune transition-transform sm:block ${
                  isProfileMenuOpen ? "rotate-180" : "rotate-0"
                }`}
              >
                ▼
              </span>
            </button>

          </div>
        </div>

        {isMobileNavOpen && (
          <div className="mx-auto w-full max-w-6xl px-6 pb-5 md:hidden">
            <div className="rounded-2xl border border-dune/20 bg-white/90 p-3 shadow-lg">
              <p className="px-2 pb-2 text-xs font-semibold uppercase tracking-[0.2em] text-dune">Navigation</p>
              <div className="space-y-1">
                {appLinks.map((link) => (
                  <Link
                    key={`mobile-${link.href}`}
                    href={link.href}
                    className="block rounded-xl px-3 py-2 text-sm text-ink transition hover:bg-bone"
                    onClick={() => setIsMobileNavOpen(false)}
                  >
                    {link.label}
                  </Link>
                ))}
              </div>
              <div className="mt-3 border-t border-dune/15 pt-3">
                <p className="px-2 text-xs text-dune">{displayName}</p>
                <button
                  type="button"
                  onClick={requestLogout}
                  className="mt-2 w-full rounded-xl px-3 py-2 text-left text-sm text-red-600 transition hover:bg-red-50"
                >
                  Logout
                </button>
              </div>
            </div>
          </div>
        )}
      </header>
      <main className="mx-auto w-full max-w-6xl px-6 py-10">{children}</main>

      {isDomReady &&
        isProfileMenuOpen &&
        createPortal(
          <div
            ref={profileDropdownRef}
            className="fixed w-56 rounded-2xl border border-dune/20 bg-white p-2 shadow-2xl"
            style={{
              top: `${profileMenuPosition.top}px`,
              right: `${profileMenuPosition.right}px`,
              zIndex: 2147483000,
            }}
          >
            <div className="rounded-xl px-3 py-2">
              <p className="truncate text-sm font-semibold text-ink">{displayName}</p>
              <p className="mt-1 text-xs text-dune">Signed in</p>
            </div>
            <Link
              href="/app/settings"
              className="mt-1 block rounded-xl px-3 py-2 text-sm text-ink transition hover:bg-bone"
              onClick={() => setIsProfileMenuOpen(false)}
            >
              Profile settings
            </Link>
            <button
              type="button"
              onClick={requestLogout}
              disabled={isLoggingOut}
              className="mt-1 w-full rounded-xl px-3 py-2 text-left text-sm text-red-600 transition hover:bg-red-50 disabled:opacity-60"
            >
              {isLoggingOut ? "Logging out..." : "Logout"}
            </button>
          </div>,
          document.body
        )}

      {isLogoutConfirmOpen && (
        <div className="ui-overlay fixed inset-0 z-[120] flex items-center justify-center bg-ink/35 px-4">
          <div className="w-full max-w-sm rounded-2xl border border-dune/20 bg-white p-5 shadow-2xl">
            <p className="text-lg font-semibold text-ink">Confirm logout</p>
            <p className="mt-2 text-sm text-dune">You will need to sign in again to continue.</p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setIsLogoutConfirmOpen(false)}
                className="rounded-full border border-dune/30 px-4 py-2 text-sm text-ink"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleLogout}
                disabled={isLoggingOut}
                className="rounded-full bg-red-600 px-4 py-2 text-sm text-white disabled:opacity-60"
              >
                {isLoggingOut ? "Logging out..." : "Logout"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
