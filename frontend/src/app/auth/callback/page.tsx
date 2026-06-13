"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "../../../lib/supabase-browser";
import { useState } from "react";

export default function AuthCallbackPage() {
  const router = useRouter();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    const run = async () => {
      const currentUrl = new URL(window.location.href);
      const code = currentUrl.searchParams.get("code");
      const authError = currentUrl.searchParams.get("error");
      const authErrorDescription = currentUrl.searchParams.get("error_description");

      if (authError) {
        setErrorMessage(authErrorDescription || authError);
        return;
      }

      // Some providers return tokens in URL hash instead of auth code.
      if (window.location.hash) {
        const hashParams = new URLSearchParams(window.location.hash.slice(1));
        const accessToken = hashParams.get("access_token");
        const refreshToken = hashParams.get("refresh_token");

        if (accessToken && refreshToken) {
          const { error: setSessionError } = await supabase.auth.setSession({
            access_token: accessToken,
            refresh_token: refreshToken,
          });
          if (setSessionError) {
            setErrorMessage(setSessionError.message);
            return;
          }
        }
      }

      // If detectSessionInUrl already completed, avoid re-exchanging the code.
      const { data: existingSessionData } = await supabase.auth.getSession();
      if (!existingSessionData.session && code) {
        const { error } = await supabase.auth.exchangeCodeForSession(code);
        if (error) {
          setErrorMessage(error.message);
          return;
        }
      }

      const { data } = await supabase.auth.getSession();
      if (!data.session) {
        setErrorMessage(
          `No session found after callback. Add ${window.location.origin}/auth/callback to Supabase Auth redirect URLs.`
        );
        return;
      }

      const userId = data.session.user?.id;
      if (!userId) {
        setErrorMessage("No authenticated user found after callback.");
        return;
      }

      const { data: preference } = await supabase
        .from("user_preferences")
        .select("user_id")
        .eq("user_id", userId)
        .maybeSingle();

      router.replace(preference ? "/app/dashboard" : "/onboarding");
    };

    run();
  }, [router]);

  return (
    <div className="baxel-shell min-h-screen">
      <main className="mx-auto flex w-full max-w-3xl items-center justify-center px-6 py-20">
        <div className="glass rounded-3xl p-10 text-center">
          <p className="label">Auth</p>
          <h1 className="mt-4 text-2xl font-semibold text-ink">
            {errorMessage ? "Sign-in failed" : "Completing sign in..."}
          </h1>
          <p className="mt-3 text-sm text-dune">
            {errorMessage || "Please wait while we secure your session."}
          </p>
        </div>
      </main>
    </div>
  );
}
