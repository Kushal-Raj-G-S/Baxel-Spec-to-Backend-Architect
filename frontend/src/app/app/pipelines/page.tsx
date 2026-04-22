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
        <p className="label">Pipeline runs</p>
        <p className="mt-2 text-sm text-dune">Live history from your stored pipeline runs.</p>

        {status ? (
          <div className="mt-6 rounded-2xl border border-dune/20 bg-white/70 px-4 py-3 text-sm text-dune">
            {status}
          </div>
        ) : (
          <div className="mt-6 space-y-3">
            {runs.map((run) => (
              <div key={run.id} className="rounded-2xl border border-dune/20 bg-white/70 px-4 py-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-ink">{run.spec_title || "Untitled spec"}</p>
                    <p className="text-xs text-dune">
                      {run.project_name || "Unknown project"} • {new Date(run.created_at).toLocaleString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-xs uppercase tracking-[0.2em] text-dune">{run.status}</span>
                    <span className="text-xs text-dune">{formatDuration(run.duration_seconds)}</span>
                    <Link
                      href={`/app/dashboard?run=${encodeURIComponent(run.id)}&project=${encodeURIComponent(run.project_name || "Saved project")}&spec=${encodeURIComponent(run.spec_title || "Untitled spec")}`}
                      className="rounded-full border border-dune/30 px-3 py-1 text-xs text-ink"
                    >
                      Open output
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
