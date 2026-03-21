"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "../../lib/supabase-browser";

type AuthMode = "signin" | "signup" | "magic";

export default function AuthPage() {
  const router = useRouter();
  const [mode, setMode] = useState<AuthMode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [workspaceName, setWorkspaceName] = useState("Baxel Studio");
  const [statusMessage, setStatusMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  const redirectTo = typeof window !== "undefined" ? `${window.location.origin}/auth/callback` : undefined;

  const signInWithProvider = async (provider: "google" | "github") => {
    setStatusMessage("Redirecting to provider...");
    const { error } = await supabase.auth.signInWithOAuth({
      provider,
      options: {
        redirectTo
      }
    });
    if (error) {
      setStatusMessage(error.message);
    }
  };

  const handleAuthSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmitting(true);
    setStatusMessage("");

    if (!email.trim()) {
      setStatusMessage("Please enter your email.");
      setIsSubmitting(false);
      return;
    }

    try {
      if (mode === "magic") {
        const { error } = await supabase.auth.signInWithOtp({
          email,
          options: { emailRedirectTo: redirectTo }
        });
        if (error) throw error;
        setStatusMessage("Magic link sent. Check your email.");
      } else if (mode === "signup") {
        const { error } = await supabase.auth.signUp({
          email,
          password,
          options: {
            emailRedirectTo: redirectTo,
            data: {
              workspace_name: workspaceName
            }
          }
        });
        if (error) throw error;
        setStatusMessage("Account created. Check your inbox for confirmation.");
      } else {
        const { error } = await supabase.auth.signInWithPassword({
          email,
          password
        });
        if (error) throw error;
        setStatusMessage("Signed in. Redirecting...");
        router.push("/app/dashboard");
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Authentication failed";
      setStatusMessage(message);
    } finally {
      setIsSubmitting(false);
    }
  };

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

  return (
    <div ref={rootRef} className="baxel-shell min-h-screen cursor-reactive">
      <div className="mx-auto w-full max-w-5xl px-6 pt-8">
        <div className="flex items-center">
          <Link
            href="/"
            className="inline-flex rounded-full border border-dune/40 bg-white/80 px-4 py-2 text-sm text-ink transition hover:bg-white"
          >
            Back to home
          </Link>
        </div>
      </div>

      <main className="mx-auto flex w-full max-w-5xl flex-col gap-10 px-6 pb-14 pt-4 lg:flex-row">
        <section className="glass flex-1 rounded-3xl p-10 reveal magnetic">
          <p className="label">Welcome</p>
          <h1 className="mt-4 text-3xl font-semibold text-ink">
            {mode === "signup" ? "Create your Baxel account." : "Sign in to continue designing."}
          </h1>
          <p className="mt-3 text-sm text-dune">
            Use your product doc, generate a backend blueprint, and push a code skeleton to your repo.
          </p>
          <div className="mt-6 grid grid-cols-3 rounded-full border border-dune/20 bg-white/70 p-1 text-[0.65rem] uppercase tracking-[0.2em] magnetic">
            {[
              { key: "signin", label: "Sign in" },
              { key: "signup", label: "Sign up" },
              { key: "magic", label: "Magic link" }
            ].map((tab) => (
              <button
                key={tab.key}
                className={`rounded-full px-3 py-2 ripple ${
                  mode === tab.key ? "bg-ink text-bone" : "text-dune"
                }`}
                onClick={() => setMode(tab.key as AuthMode)}
                type="button"
              >
                {tab.label}
              </button>
            ))}
          </div>
          <div className="mt-6 flex flex-col gap-3">
            <button
              className="rounded-full bg-ink px-4 py-2 text-sm text-bone ripple"
              onClick={() => signInWithProvider("google")}
              type="button"
            >
              Continue with Google
            </button>
            <button
              className="rounded-full border border-dune/40 px-4 py-2 text-sm ripple"
              onClick={() => signInWithProvider("github")}
              type="button"
            >
              Continue with Github
            </button>
          </div>
          <div className="my-6 flex items-center gap-4 text-xs text-dune">
            <span className="h-px w-full bg-dune/20" />
            Or
            <span className="h-px w-full bg-dune/20" />
          </div>
          <form className="space-y-4" onSubmit={handleAuthSubmit}>
            <div>
              <label className="text-xs uppercase tracking-[0.2em] text-dune">Email</label>
              <input
                className="mt-2 w-full rounded-2xl border border-dune/20 bg-white/70 px-4 py-3 text-sm"
                placeholder="you@company.com"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </div>
            {mode !== "magic" && (
              <div>
                <label className="text-xs uppercase tracking-[0.2em] text-dune">Password</label>
                <input
                  className="mt-2 w-full rounded-2xl border border-dune/20 bg-white/70 px-4 py-3 text-sm"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </div>
            )}
            {mode === "signup" && (
              <div>
                <label className="text-xs uppercase tracking-[0.2em] text-dune">Workspace name</label>
                <input
                  className="mt-2 w-full rounded-2xl border border-dune/20 bg-white/70 px-4 py-3 text-sm"
                  placeholder="Baxel Studio"
                  value={workspaceName}
                  onChange={(event) => setWorkspaceName(event.target.value)}
                />
              </div>
            )}
            {mode === "signin" && (
              <div className="flex items-center justify-between text-xs text-dune">
                <label className="flex items-center gap-2">
                  <input type="checkbox" className="h-4 w-4 rounded border-dune/40" />
                  Remember me
                </label>
                <span>Forgot password?</span>
              </div>
            )}
            <button className="w-full rounded-full bg-ink px-4 py-3 text-sm text-bone ripple" disabled={isSubmitting}>
              {mode === "signup" ? "Create account" : mode === "magic" ? "Send magic link" : "Sign in"}
            </button>
            {statusMessage && <p className="text-xs text-dune">{statusMessage}</p>}
          </form>
        </section>
        <aside className="glass flex-1 rounded-3xl p-10 reveal reveal-delay-1 magnetic">
          <p className="label">Preview</p>
          <h2 className="mt-4 text-2xl font-semibold text-ink">After auth, you land on the dashboard.</h2>
          <p className="mt-3 text-sm text-dune">
            Track pipeline runs, update ERDs, and export code bundles from one workspace.
          </p>
          <Link
            href="/app/dashboard"
            className="mt-6 inline-flex rounded-full border border-dune/40 px-4 py-2 text-sm ripple"
          >
            Go to dashboard
          </Link>
          <div className="mt-8 rounded-2xl border border-dune/20 bg-white/70 p-5 magnetic">
            <p className="text-xs uppercase tracking-[0.2em] text-dune">New here?</p>
            <p className="mt-3 text-sm text-ink">Create a workspace and invite teammates in minutes.</p>
            <button
              className="mt-4 rounded-full bg-ink px-4 py-2 text-sm text-bone ripple"
              onClick={() => setMode("signup")}
              type="button"
            >
              Start a workspace
            </button>
          </div>
        </aside>
      </main>
    </div>
  );
}
