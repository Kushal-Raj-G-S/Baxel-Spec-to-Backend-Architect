"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import AppShell from "../../components/app-shell";
import { supabase } from "../../../lib/supabase-browser";

type PipelineRun = {
  id: string;
  status: string;
  created_at: string;
  completed_at?: string | null;
  project_name?: string | null;
  spec_title?: string | null;
  duration_seconds?: number | null;
  spec_id?: string | null;
};

const formatDuration = (value?: number | null) => {
  if (value === null || value === undefined) return "-";
  if (value < 60) return `${value}s`;
  const minutes = Math.floor(value / 60);
  const seconds = value % 60;
  return `${minutes}m ${seconds.toString().padStart(2, "0")}s`;
};

export default function PipelinesPage() {
  const apiBaseUrl = useMemo(
    () => process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000",
    []
  );
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [status, setStatus] = useState("Loading pipeline history...");

  useEffect(() => {
    const loadRuns = async () => {
      try {
        const { data } = await supabase.auth.getSession();
        const token = data.session?.access_token;
        if (!token) {
          setStatus("Please sign in to view pipelines");
          return;
        }

        const response = await fetch(`${apiBaseUrl}/pipelines/history`, {
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`
          }
        });

        if (!response.ok) {
          throw new Error("Failed to load pipelines");
        }

        const dataRows = await response.json();
        setRuns(Array.isArray(dataRows) ? dataRows : []);
        setStatus(Array.isArray(dataRows) && dataRows.length ? "" : "No pipeline runs yet.");
      } catch {
        setStatus("Unable to load pipelines right now.");
      }
    };

    loadRuns();
  }, [apiBaseUrl]);

  return (
    <AppShell>
      <div className="glass rounded-3xl p-8">
        <p className="label">SAGE Conversations</p>
        <p className="mt-2 text-sm text-white/60">Reopen and resume your historical SAGE chats.</p>

        {status ? (
          <div className="mt-6 rounded-2xl border border-white/20 bg-white/5 px-4 py-3 text-sm text-white/80">
            {status}
          </div>
        ) : (
          <div className="mt-6 space-y-3">
            {runs.map((run) => (
              <div key={run.id} className="rounded-2xl border border-white/20 bg-white/5 px-4 py-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-white">{run.spec_title || "Untitled spec"}</p>
                    <p className="text-xs text-white/60">
                      {run.project_name || "Unknown project"} • {new Date(run.created_at).toLocaleString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <Link
                      href={`/app/chatbot?run=${encodeURIComponent(run.id)}&spec_id=${encodeURIComponent(run.spec_id || "")}&title=${encodeURIComponent(run.spec_title || "Generated Spec")}&project=${encodeURIComponent(run.project_name || "Default Project")}`}
                      className="rounded-full bg-[#C2D68C] px-4 py-1.5 text-xs font-semibold text-[#1F261D] transition-all hover:bg-[#b0c878]"
                    >
                      Resume Chat
                    </Link>
                    <Link
                      href={`/app/dashboard?run=${encodeURIComponent(run.id)}&project=${encodeURIComponent(run.project_name || "Saved project")}&spec=${encodeURIComponent(run.spec_title || "Untitled spec")}`}
                      className="rounded-full border border-white/20 bg-white/5 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-white/10 hover:border-white/40"
                    >
                      Open Workspace
                    </Link>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
