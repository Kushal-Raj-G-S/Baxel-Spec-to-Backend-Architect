"use client";

import { useEffect, useMemo, useState } from "react";
import AppShell from "../../components/app-shell";
import { supabase } from "../../../lib/supabase-browser";
import { resolveAvatarUrl } from "../../../lib/avatar";

type Profile = {
  id: string;
  email?: string;
  username?: string;
  full_name?: string;
  avatar_url?: string;
};

type PlanSummary = {
  plan_name: string;
  status: string;
  monthly_run_limit: number;
  runs_used_this_month: number;
  billing_period?: string | null;
  period_start?: string | null;
  period_end?: string | null;
  manage_url?: string | null;
};

export default function SettingsPage() {
  const apiBaseUrl = useMemo(
    () => process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000",
    []
  );

  const [profile, setProfile] = useState<Profile | null>(null);
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [statusMessage, setStatusMessage] = useState("Loading profile...");
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [avatarDisplayUrl, setAvatarDisplayUrl] = useState<string | null>(null);
  const [plan, setPlan] = useState<PlanSummary | null>(null);

  const getAccessToken = async () => {
    const { data } = await supabase.auth.getSession();
    return data.session?.access_token || null;
  };

  const getAuthHeaders = (token: string) => ({
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`
  });

  const loadProfile = async () => {
    try {
      const [{ data: userData }, token] = await Promise.all([
        supabase.auth.getUser(),
        getAccessToken()
      ]);

      const user = userData.user;
      if (!token) {
        setEmail(user?.email || "");
        setUsername(user?.email?.split("@")[0] || "");
        setFullName(user?.user_metadata?.full_name || "");
        setStatusMessage("Please sign in from /auth first");
        return;
      }

      const profileHeaders = getAuthHeaders(token);
      const [profileResponse, planResponse] = await Promise.all([
        fetch(`${apiBaseUrl}/profile/me`, { headers: profileHeaders }),
        fetch(`${apiBaseUrl}/profile/plan`, { headers: profileHeaders })
      ]);

      if (!profileResponse.ok) {
        throw new Error("Failed to load profile");
      }

      const data: Profile = await profileResponse.json();
      const emailValue = data.email || user?.email || "";
      const fallbackUsername = emailValue.includes("@") ? emailValue.split("@")[0] : "";

      setProfile(data);
      setAvatarDisplayUrl(await resolveAvatarUrl(data.avatar_url));
      setEmail(emailValue);
      setUsername(data.username || fallbackUsername);
      setFullName(data.full_name || user?.user_metadata?.full_name || "");
      if (planResponse.ok) {
        const planData: PlanSummary = await planResponse.json();
        setPlan(planData);
      }
      setStatusMessage("Profile loaded");
    } catch (error) {
      setStatusMessage("Unable to load profile");
    }
  };

  useEffect(() => {
    loadProfile();
  }, []);

  const saveProfile = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setStatusMessage("Saving profile...");

    try {
      const token = await getAccessToken();
      if (!token) {
        setStatusMessage("Please sign in from /auth first");
        return;
      }

      const headers = getAuthHeaders(token);
      const response = await fetch(`${apiBaseUrl}/profile/me`, {
        method: "PATCH",
        headers,
        body: JSON.stringify({
          username: username.trim().toLowerCase() || null,
          full_name: fullName || null,
          avatar_url: profile?.avatar_url || null
        })
      });

      if (!response.ok) {
        const errorBody = await response.json().catch(() => ({}));
        throw new Error(errorBody.detail || "Failed to save profile");
      }

      const data: Profile = await response.json();
      setProfile(data);
      setAvatarDisplayUrl(await resolveAvatarUrl(data.avatar_url));
      setStatusMessage("Profile updated");
    } catch (error) {
      if (error instanceof Error && error.message.includes("Username is already taken")) {
        setStatusMessage("Username is already taken");
      } else {
        setStatusMessage("Could not save profile");
      }
    } finally {
      setSaving(false);
    }
  };

  const uploadAvatar = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      setUploading(true);
      setStatusMessage("Uploading photo...");

      const { data: userData } = await supabase.auth.getUser();
      const userId = userData.user?.id;
      if (!userId) {
        throw new Error("User not signed in");
      }

      const token = await getAccessToken();
      if (!token) {
        setStatusMessage("Please sign in from /auth first");
        return;
      }

      const ext = file.name.split(".").pop() || "jpg";
      const path = `${userId}/avatar-${Date.now()}.${ext}`;
      const upload = await supabase.storage.from("avatars").upload(path, file, { upsert: true });

      if (upload.error) {
        throw upload.error;
      }

      const headers = getAuthHeaders(token);
      const response = await fetch(`${apiBaseUrl}/profile/me`, {
        method: "PATCH",
        headers,
        body: JSON.stringify({
          username: username.trim().toLowerCase() || null,
          full_name: fullName || null,
          avatar_url: path
        })
      });

      if (!response.ok) {
        throw new Error("Failed to save avatar URL");
      }

      const data: Profile = await response.json();
      setProfile(data);
      setAvatarDisplayUrl(await resolveAvatarUrl(data.avatar_url));
      setStatusMessage("Profile photo updated");
    } catch (error) {
      setStatusMessage("Avatar upload failed. Check avatars bucket and RLS policies.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <AppShell>
      <div className="glass rounded-3xl p-8">
        <p className="label">Settings</p>
        <h1 className="mt-3 text-2xl font-semibold text-ink">Profile</h1>
        <p className="mt-2 text-sm text-dune">Update your account details and profile photo.</p>

        <div className="mt-6 flex items-center gap-4">
          {avatarDisplayUrl ? (
            <img src={avatarDisplayUrl} alt="Profile" className="h-16 w-16 rounded-full object-cover" />
          ) : (
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-ink text-bone text-lg">
              {(fullName || email || "U").slice(0, 1).toUpperCase()}
            </div>
          )}
          <label className="rounded-full border border-dune/40 px-4 py-2 text-sm cursor-pointer">
            {uploading ? "Uploading..." : "Upload photo"}
            <input type="file" accept="image/*" className="hidden" onChange={uploadAvatar} />
          </label>
        </div>

        <div className="mt-10 rounded-2xl border border-dune/20 bg-white/70 p-5">
          <p className="text-xs uppercase tracking-[0.2em] text-dune">Plan & Billing</p>
          <h2 className="mt-2 text-xl font-semibold text-ink">{plan?.plan_name || "Starter"}</h2>
          <p className="mt-1 text-sm text-dune">
            Status: {(plan?.status || "active").toUpperCase()} • {plan?.runs_used_this_month ?? 0}/{plan?.monthly_run_limit ?? 3} runs used this month
          </p>
          <p className="mt-2 text-xs text-dune">
            Billing period: {plan?.billing_period || `${plan?.period_start ? new Date(plan.period_start).toLocaleDateString() : "-"} to ${plan?.period_end ? new Date(plan.period_end).toLocaleDateString() : "-"}`}
          </p>
          {plan?.manage_url ? (
            <a
              href={plan.manage_url}
              target="_blank"
              rel="noreferrer"
              className="mt-4 inline-block rounded-full border border-dune/40 px-4 py-2 text-sm text-ink"
            >
              Manage billing
            </a>
          ) : (
            <button className="mt-4 rounded-full border border-dune/40 px-4 py-2 text-sm text-ink">
              Upgrade plan
            </button>
          )}
        </div>

        <form className="mt-8 space-y-4" onSubmit={saveProfile}>
          <div>
            <label className="text-xs uppercase tracking-[0.2em] text-dune">Email</label>
            <input
              className="mt-2 w-full rounded-2xl border border-dune/20 bg-white/70 px-4 py-3 text-sm"
              value={email}
              disabled
            />
          </div>

          <div>
            <label className="text-xs uppercase tracking-[0.2em] text-dune">Username</label>
            <input
              className="mt-2 w-full rounded-2xl border border-dune/20 bg-white/70 px-4 py-3 text-sm"
              value={username}
              onChange={(event) => setUsername(event.target.value.replace(/\s+/g, "").toLowerCase())}
              placeholder="your-username"
            />
          </div>

          <div>
            <label className="text-xs uppercase tracking-[0.2em] text-dune">Full name</label>
            <input
              className="mt-2 w-full rounded-2xl border border-dune/20 bg-white/70 px-4 py-3 text-sm"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              placeholder="Your full name"
            />
          </div>

          <button className="rounded-full bg-ink px-5 py-2 text-sm text-bone" disabled={saving}>
            {saving ? "Saving..." : "Save changes"}
          </button>
          <p className="text-xs text-dune">{statusMessage}</p>
        </form>
      </div>
    </AppShell>
  );
}
