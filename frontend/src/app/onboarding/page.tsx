"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "../../lib/supabase-browser";

type PreferenceRole = "solo_dev" | "founder" | "backend_engineer" | "student";
type PreferenceIntent = "new_build" | "prototype" | "document" | "explore";
type PreferenceExperience = "beginner" | "intermediate" | "advanced";
type PreferenceHeardAbout = "linkedin" | "product_hunt" | "google" | "other";

type UserPreferenceRow = {
  user_id: string;
  role: PreferenceRole;
  intent: PreferenceIntent;
  experience: PreferenceExperience;
  heard_about: PreferenceHeardAbout;
  heard_about_other?: string | null;
  created_at?: string;
};

const roleOptions: Array<{ label: string; value: PreferenceRole }> = [
  { label: "Solo developer", value: "solo_dev" },
  { label: "Startup founder", value: "founder" },
  { label: "Backend engineer", value: "backend_engineer" },
  { label: "Student / learning", value: "student" }
];

const intentOptions: Array<{ label: string; value: PreferenceIntent }> = [
  { label: "Build something new", value: "new_build" },
  { label: "Prototype quickly", value: "prototype" },
  { label: "Document a system", value: "document" },
  { label: "Just exploring", value: "explore" }
];

const experienceOptions: Array<{ label: string; value: PreferenceExperience }> = [
  { label: "Beginner", value: "beginner" },
  { label: "Intermediate", value: "intermediate" },
  { label: "Advanced", value: "advanced" }
];

const heardAboutOptions: Array<{ label: string; value: PreferenceHeardAbout }> = [
  { label: "LinkedIn", value: "linkedin" },
  { label: "Product Hunt", value: "product_hunt" },
  { label: "Google", value: "google" },
  { label: "Others", value: "other" }
];

export default function OnboardingPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [statusMessage, setStatusMessage] = useState("Checking your workspace...");

  const [role, setRole] = useState<PreferenceRole | null>(null);
  const [intent, setIntent] = useState<PreferenceIntent | null>(null);
  const [experience, setExperience] = useState<PreferenceExperience | null>(null);
  const [heardAbout, setHeardAbout] = useState<PreferenceHeardAbout | null>(null);
  const [heardAboutOther, setHeardAboutOther] = useState("");

  const canContinue = useMemo(
    () => !!role && !!intent && !!experience,
    [role, intent, experience]
  );

  useEffect(() => {
    const load = async () => {
      const { data: userData } = await supabase.auth.getUser();
      const user = userData.user;
      if (!user) {
        router.replace("/auth");
        return;
      }

      const { data: existingPreference, error } = await supabase
        .from("user_preferences")
        .select("user_id")
        .eq("user_id", user.id)
        .maybeSingle();

      if (!error && existingPreference) {
        router.replace("/app/dashboard");
        return;
      }

      setLoading(false);
      setStatusMessage("Takes 30 seconds. You can change this anytime.");
    };

    load();
  }, [router]);

  const savePreference = async () => {
    if (!canContinue || saving) return;

    setSaving(true);
    setStatusMessage("Saving your preferences...");

    try {
      const { data: userData } = await supabase.auth.getUser();
      const user = userData.user;
      if (!user) {
        router.replace("/auth");
        return;
      }

      const payload: UserPreferenceRow = {
        user_id: user.id,
        role: role!,
        intent: intent!,
        experience: experience!,
        heard_about: heardAbout || "other",
        heard_about_other: heardAbout === "other" ? heardAboutOther.trim() : null
      };

      const { error } = await supabase.from("user_preferences").upsert(payload, { onConflict: "user_id" });
      if (error) {
        setStatusMessage("Could not save preferences. Please try again.");
        return;
      }

      router.replace("/app/dashboard");
    } finally {
      setSaving(false);
    }
  };

  const renderOption = <T extends string>(
    option: { label: string; value: T },
    selectedValue: T | null,
    onSelect: (value: T) => void
  ) => {
    const active = selectedValue === option.value;
    return (
      <button
        key={option.value}
        type="button"
        onClick={() => onSelect(option.value)}
        className={`rounded-xl border px-4 py-3 text-sm transition ${
          active
            ? "border-ink bg-ink text-bone"
            : "border-dune/25 bg-white text-ink hover:border-dune/45"
        }`}
      >
        {option.label}
      </button>
    );
  };

  return (
    <div className="baxel-shell relative min-h-screen overflow-hidden">
      <div className="pointer-events-none absolute -left-24 top-10 h-64 w-64 rounded-full bg-[#f2d6b3]/35 blur-3xl" />
      <div className="pointer-events-none absolute -right-20 bottom-6 h-72 w-72 rounded-full bg-[#cdd5bf]/35 blur-3xl" />
      <main className="relative mx-auto flex min-h-screen w-full max-w-5xl items-center justify-center px-6 py-12">
        <section className="glass w-full max-w-3xl rounded-3xl border border-dune/25 bg-white/90 p-8 shadow-[0_28px_90px_rgba(13,13,13,0.18)] md:p-10">
          <div className="mb-6 flex items-center justify-center gap-2">
            <span className={`h-2 w-2 rounded-full ${role ? "bg-ink" : "bg-dune/25"}`} />
            <span className={`h-2 w-2 rounded-full ${intent ? "bg-ink" : "bg-dune/25"}`} />
            <span className={`h-2 w-2 rounded-full ${experience ? "bg-ink" : "bg-dune/25"}`} />
          </div>

          <h1 className="text-center text-3xl font-semibold text-ink">Let&apos;s set up your workspace</h1>
          <p className="mt-2 text-center text-sm text-dune">Takes 30 seconds. You can change this anytime.</p>

          <div className="mt-8 space-y-5">
            <div className="rounded-2xl border border-dune/20 bg-white/80 p-4">
              <p className="text-sm font-medium text-ink">What best describes you?</p>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                {roleOptions.map((option) => renderOption(option, role, setRole))}
              </div>
            </div>

            <div className="rounded-2xl border border-dune/20 bg-white/80 p-4">
              <p className="text-sm font-medium text-ink">What are you here to do?</p>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                {intentOptions.map((option) => renderOption(option, intent, setIntent))}
              </div>
            </div>

            <div className="rounded-2xl border border-dune/20 bg-white/80 p-4">
              <p className="text-sm font-medium text-ink">Your database design experience?</p>
              <div className="mt-3 grid gap-3 sm:grid-cols-3">
                {experienceOptions.map((option) => renderOption(option, experience, setExperience))}
              </div>
            </div>

            <div className="rounded-2xl border border-dune/20 bg-white/80 p-4">
              <p className="text-sm font-medium text-ink">Where did you hear about us?</p>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                {heardAboutOptions.map((option) => renderOption(option, heardAbout, setHeardAbout))}
              </div>
              {heardAbout === "other" ? (
                <input
                  className="mt-3 w-full rounded-xl border border-dune/25 bg-white px-3 py-2 text-sm text-ink"
                  placeholder="Tell us where..."
                  value={heardAboutOther}
                  onChange={(event) => setHeardAboutOther(event.target.value)}
                />
              ) : null}
            </div>
          </div>

          <div className="mt-8 flex items-center justify-between gap-4">
            <p className="text-xs text-dune">{loading ? "Loading..." : statusMessage}</p>
            <button
              type="button"
              disabled={!canContinue || saving || loading}
              onClick={savePreference}
              className={`rounded-full px-6 py-2.5 text-sm font-medium shadow-[0_10px_22px_rgba(20,20,20,0.25)] ${
                canContinue && !saving && !loading
                  ? "bg-ink text-bone"
                  : "cursor-not-allowed border border-dune/30 bg-white text-dune"
              }`}
            >
              {saving ? "Saving..." : "Continue ->"}
            </button>
          </div>

          {!canContinue ? (
            <p className="mt-2 text-right text-xs text-dune">Answer all questions to continue</p>
          ) : null}
        </section>
      </main>
    </div>
  );
}
