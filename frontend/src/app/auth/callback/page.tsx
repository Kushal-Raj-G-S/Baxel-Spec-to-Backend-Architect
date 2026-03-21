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

      if (code) {
        const { error } = await supabase.auth.exchangeCodeForSession(code);
        if (error) {
          setErrorMessage(error.message);
          return;
        }
      }

      const { data } = await supabase.auth.getSession();
      if (!data.session) {
        setErrorMessage("No session found after callback. Check Supabase redirect URLs.");
        return;
      }

      router.replace("/app/dashboard");
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
