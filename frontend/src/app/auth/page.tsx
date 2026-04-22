"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "../../lib/supabase-browser";

type AuthMode = "signin" | "signup" | "magic";

import MarketingShell from "../components/marketing-shell";

export default function AuthPage() {
  const router = useRouter();
  const [mode, setMode] = useState<AuthMode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [workspaceName, setWorkspaceName] = useState("Baxel Studio");
  const [statusMessage, setStatusMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

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

  return (
    <MarketingShell>
      <main className="mx-auto flex w-full max-w-5xl flex-col gap-10 px-6 pb-14 pt-24 lg:flex-row relative z-10">
        <section className="flex-1 rounded-[2.5rem] bg-[#1F261D] border border-black/5 shadow-2xl p-10 reveal magnetic">
          <p className="text-xs uppercase tracking-[0.2em] text-[#C2D68C]">Welcome</p>
          <h1 className="mt-4 text-3xl font-semibold text-white">
            {mode === "signup" ? "Create your Baxel account." : "Sign in to continue designing."}
          </h1>
          <p className="mt-3 text-sm text-white/60">
            Use your product doc, generate a backend blueprint, and push a code skeleton to your repo.
          </p>
          <div className="mt-6 grid grid-cols-3 rounded-full border border-white/10 bg-white/5 p-1 text-[0.65rem] uppercase tracking-[0.2em] magnetic">
            {[
              { key: "signin", label: "Sign in" },
              { key: "signup", label: "Sign up" },
              { key: "magic", label: "Magic link" }
            ].map((tab) => (
              <button
                key={tab.key}
                className={`rounded-full px-3 py-2 transition-colors ${
                  mode === tab.key ? "bg-[#C2D68C] text-[#1F261D] font-bold shadow-sm" : "text-white/60 hover:text-white"
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
              className="rounded-full bg-white/10 hover:bg-white/20 transition-colors border border-white/5 px-4 py-3 text-sm text-white font-medium"
              onClick={() => signInWithProvider("google")}
              type="button"
            >
              Continue with Google
            </button>
            <button
              className="rounded-full bg-white/10 hover:bg-white/20 transition-colors border border-white/5 px-4 py-3 text-sm text-white font-medium"
              onClick={() => signInWithProvider("github")}
              type="button"
            >
              Continue with Github
            </button>
          </div>
          <div className="my-6 flex items-center gap-4 text-xs text-white/40">
            <span className="h-px w-full bg-white/10" />
            Or
            <span className="h-px w-full bg-white/10" />
          </div>
          <form className="space-y-4" onSubmit={handleAuthSubmit}>
            <div>
              <label className="text-xs uppercase tracking-[0.2em] text-white/50">Email</label>
              <input
                className="mt-2 w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white placeholder-white/30 focus:outline-none focus:border-[#C2D68C]"
                placeholder="you@company.com"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </div>
            {mode !== "magic" && (
              <div>
                <label className="text-xs uppercase tracking-[0.2em] text-white/50">Password</label>
                <input
                  className="mt-2 w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white placeholder-white/30 focus:outline-none focus:border-[#C2D68C]"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </div>
            )}
            {mode === "signup" && (
              <div>
                <label className="text-xs uppercase tracking-[0.2em] text-white/50">Workspace name</label>
                <input
                  className="mt-2 w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white placeholder-white/30 focus:outline-none focus:border-[#C2D68C]"
                  placeholder="Baxel Studio"
                  value={workspaceName}
                  onChange={(event) => setWorkspaceName(event.target.value)}
                />
              </div>
            )}
            {mode === "signin" && (
              <div className="flex items-center justify-between text-xs text-white/50">
                <label className="flex items-center gap-2 cursor-pointer hover:text-white transition-colors">
                  <input type="checkbox" className="h-4 w-4 rounded border-white/20 bg-white/5 accent-[#C2D68C]" />
                  Remember me
                </label>
                <span className="cursor-pointer hover:text-white transition-colors">Forgot password?</span>
              </div>
            )}
            <button className="w-full rounded-full bg-[#C2D68C] px-4 py-3 text-sm font-bold text-[#1F261D] shadow-[0_0_15px_rgba(194,214,140,0.3)] transition hover:scale-[1.02]" disabled={isSubmitting}>
              {mode === "signup" ? "Create account" : mode === "magic" ? "Send magic link" : "Sign in"}
            </button>
            {statusMessage && <p className="text-xs text-[#C2D68C]">{statusMessage}</p>}
          </form>
        </section>
        
        <aside className="flex-1 rounded-[2.5rem] bg-[#1F261D] border border-black/5 shadow-2xl p-10 reveal reveal-delay-1 magnetic">
          <p className="text-xs uppercase tracking-[0.2em] text-[#C2D68C]">Preview</p>
          <h2 className="mt-4 text-2xl font-semibold text-white">After auth, you land on the dashboard.</h2>
          <p className="mt-3 text-sm text-white/60">
            Track pipeline runs, update ERDs, and export code bundles from one workspace.
          </p>
          <Link
            href="/app/dashboard"
            className="mt-6 inline-flex rounded-full border border-white/20 bg-white/5 hover:bg-white/10 px-5 py-2.5 text-sm font-medium text-white transition-colors"
          >
            Go to dashboard
          </Link>
          <div className="mt-8 rounded-2xl border border-white/10 bg-white/5 p-6 magnetic">
            <p className="text-xs uppercase tracking-[0.2em] text-[#C2D68C]">New here?</p>
            <p className="mt-3 text-sm text-white">Create a workspace and invite teammates in minutes.</p>
            <button
              className="mt-4 rounded-full bg-white px-5 py-2.5 text-sm font-semibold text-[#1F261D] transition hover:scale-[1.02]"
              onClick={() => setMode("signup")}
              type="button"
            >
              Start a workspace
            </button>
          </div>
        </aside>
      </main>
    </MarketingShell>
  );
}
