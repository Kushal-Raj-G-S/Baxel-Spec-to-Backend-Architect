"use client";

import { useEffect, useMemo, useState } from "react";
import AppShell from "../../components/app-shell";
import { supabase } from "../../../lib/supabase-browser";

type PipelineResult = {
  entities?: Array<{ name: string }>;
  relationships?: string[];
  endpoints?: Array<{ method: string; path: string; desc?: string }>;
  rules?: Array<string | { name?: string }>;
  migration_sql?: string | string[] | Array<string | string[]>;
};

type ProjectHistory = {
  project: {
    id: string;
    name: string;
    description?: string | null;
    created_at: string;
  };
  specs_count: number;
  pipeline_runs_count: number;
  recent_runs: Array<{
    id: string;
    status: string;
    created_at: string;
    spec_id?: string | null;
    spec_title?: string | null;
    result?: PipelineResult | null;
  }>;
};

export default function ProjectsPage() {
  const apiBaseUrl = useMemo(
    () => process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000",
    []
  );
  const [projects, setProjects] = useState<ProjectHistory[]>([]);
  const [status, setStatus] = useState("Loading projects...");
  const [selectedRun, setSelectedRun] = useState<{
    projectName: string;
    specTitle?: string | null;
    runId: string;
    runLabel: string;
    result?: PipelineResult | null;
  } | null>(null);
  const [shareStatus, setShareStatus] = useState("");

  const getAuthHeaders = (token: string) => ({
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`
  });

  const createShareLink = async (runId: string) => {
    try {
      setShareStatus("Creating share link...");
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token;
      if (!token) {
        setShareStatus("Please sign in to create share links.");
        return;
      }

      const response = await fetch(`${apiBaseUrl}/runs/${runId}/share`, {
        headers: getAuthHeaders(token)
      });
      if (!response.ok) {
        setShareStatus("Unable to create share link.");
        return;
      }

      const payload = await response.json();
      const shareUrl = `${window.location.origin}/share/${payload.token}`;
      await navigator.clipboard.writeText(shareUrl);
      setShareStatus("Share URL copied to clipboard.");
    } catch {
      setShareStatus("Unable to create share link.");
    }
  };

  useEffect(() => {
    const loadProjects = async () => {
      try {
        const { data } = await supabase.auth.getSession();
        const token = data.session?.access_token;

        if (!token) {
          setStatus("Please sign in to view your projects");
          return;
        }

        const headers = getAuthHeaders(token);

        const projectsRes = await fetch(`${apiBaseUrl}/projects/history`, { headers });
        if (!projectsRes.ok) {
          throw new Error("Failed to fetch projects history");
        }

        const historyList = await projectsRes.json();
        if (!Array.isArray(historyList) || !historyList.length) {
          setProjects([]);
          setStatus("No projects yet. Run a spec from dashboard to create one.");
          return;
        }

        const validHistories = historyList as ProjectHistory[];

        const groupedMap = new Map<string, ProjectHistory>();
        validHistories.forEach((item) => {
          const key = item.project.name.trim().toLowerCase();
          const existing = groupedMap.get(key);
          if (!existing) {
            groupedMap.set(key, {
              ...item,
              recent_runs: [...item.recent_runs],
            });
            return;
          }

          existing.specs_count += item.specs_count;
          existing.pipeline_runs_count += item.pipeline_runs_count;
          existing.recent_runs = [...existing.recent_runs, ...item.recent_runs]
            .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
            .slice(0, 20);
        });

        const dedupedProjects = Array.from(groupedMap.values())
          .filter((item) => item.pipeline_runs_count > 0)
          .sort(
            (a, b) =>
              new Date(b.recent_runs[0]?.created_at || b.project.created_at).getTime() -
              new Date(a.recent_runs[0]?.created_at || a.project.created_at).getTime()
          );

        setProjects(dedupedProjects);
        setStatus(dedupedProjects.length ? "" : "No projects with pipeline runs yet.");
      } catch {
        setStatus("Unable to load projects right now. Check backend connection.");
      }
    };

    loadProjects();
  }, [apiBaseUrl]);

  const selectedResult = selectedRun?.result;
  const entities = selectedResult?.entities || [];
  const endpoints = selectedResult?.endpoints || [];
  const relationships = selectedResult?.relationships || [];
  const rules = selectedResult?.rules || [];
  const sql = selectedResult?.migration_sql;
  const sqlText = Array.isArray(sql) ? sql.flat(Infinity as 1).join("\n\n") : String(sql || "");
  const isLegacyRun =
    !!selectedResult &&
    (entities.length > 0 || endpoints.length > 0 || rules.length > 0) &&
    !relationships.length &&
    !sqlText.trim();

  return (
    <AppShell>
      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <section className="glass rounded-3xl p-8">
          <p className="label">Projects history</p>
          <p className="mt-2 text-sm text-dune">Stored projects, runs, and outputs from your account.</p>

          {status ? (
            <div className="mt-6 rounded-2xl border border-dune/20 bg-white/70 px-4 py-3 text-sm text-dune">
              {status}
            </div>
          ) : (
            <div className="mt-6 space-y-4">
              {projects.map((item) => (
                <div key={item.project.id} className="rounded-2xl border border-dune/20 bg-white/70 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-ink">{item.project.name}</p>
                      {item.project.description ? (
                        <p className="mt-1 text-xs text-dune">{item.project.description}</p>
                      ) : null}
                    </div>
                    <p className="text-[11px] uppercase tracking-[0.16em] text-dune">
                      {item.specs_count} specs • {item.pipeline_runs_count} runs
                    </p>
                  </div>

                  <div className="mt-3 space-y-2">
                    {item.recent_runs.length ? (
                      item.recent_runs.map((run) => (
                        <div
                          key={run.id}
                          className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-dune/20 bg-bone/90 px-3 py-2"
                        >
                          <div>
                            <p className="text-xs font-medium text-ink">
                              {run.spec_title || "Untitled spec"}
                            </p>
                            <p className="text-[11px] text-dune">
                              {new Date(run.created_at).toLocaleString()} • {run.status}
                            </p>
                          </div>
                          <button
                            className="rounded-full border border-dune/30 px-3 py-1 text-xs text-ink"
                            onClick={() =>
                              setSelectedRun({
                                projectName: item.project.name,
                                specTitle: run.spec_title,
                                runId: run.id,
                                runLabel: `${run.spec_title || "Untitled spec"} • ${new Date(run.created_at).toLocaleString()}`,
                                result: run.result,
                              })
                            }
                          >
                            View output
                          </button>
                          <button
                            className="rounded-full border border-dune/30 px-3 py-1 text-xs text-ink"
                            onClick={() => createShareLink(run.id)}
                          >
                            Share
                          </button>
                        </div>
                      ))
                    ) : (
                      <p className="text-xs text-dune">No pipeline runs for this project yet.</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="glass rounded-3xl p-8">
          <p className="label">Saved output preview</p>
          {selectedRun ? (
            <div className="mt-4 space-y-4 text-sm text-dune">
              <div>
                <p className="text-ink font-semibold">{selectedRun.projectName}</p>
                <p className="text-xs">{selectedRun.specTitle || "Untitled spec"}</p>
                <p className="text-[11px]">{selectedRun.runLabel}</p>
              </div>

              {isLegacyRun ? (
                <div className="rounded-xl border border-amber-300/70 bg-amber-50 p-3 text-xs text-amber-900">
                  This run predates full output capture. Re-run this spec to generate complete relationships and SQL.
                </div>
              ) : null}

              <button
                className="rounded-full border border-dune/30 px-4 py-2 text-xs text-ink"
                onClick={() => createShareLink(selectedRun.runId)}
              >
                Share this output
              </button>
              {shareStatus ? <p className="text-xs text-dune">{shareStatus}</p> : null}

              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl border border-dune/20 bg-white/70 p-3">
                  <p className="text-[11px] uppercase tracking-[0.16em]">Entities</p>
                  <p className="mt-2 text-lg font-semibold text-ink">{entities.length}</p>
                </div>
                <div className="rounded-xl border border-dune/20 bg-white/70 p-3">
                  <p className="text-[11px] uppercase tracking-[0.16em]">Endpoints</p>
                  <p className="mt-2 text-lg font-semibold text-ink">{endpoints.length}</p>
                </div>
              </div>

              <div className="rounded-xl border border-dune/20 bg-white/70 p-3">
                <p className="text-[11px] uppercase tracking-[0.16em]">Relationships</p>
                <p className="mt-2 text-xs text-ink">{relationships.join(" • ") || "No relationships captured for this run."}</p>
              </div>

              <div className="rounded-xl border border-dune/20 bg-white/70 p-3">
                <p className="text-[11px] uppercase tracking-[0.16em]">Rules</p>
                <p className="mt-2 text-xs text-ink">
                  {rules.length
                    ? rules
                        .slice(0, 4)
                        .map((rule) => (typeof rule === "string" ? rule : rule.name || "Rule"))
                        .join(" • ")
                    : "No rules in saved result."}
                </p>
              </div>

              <div className="rounded-xl border border-dune/20 bg-white/70 p-3">
                <p className="text-[11px] uppercase tracking-[0.16em]">Migration SQL</p>
                <pre className="mt-2 max-h-36 overflow-auto text-[11px] text-ink whitespace-pre-wrap">
                  {sqlText || "No SQL captured for this run."}
                </pre>
              </div>
            </div>
          ) : (
            <p className="mt-4 text-sm text-dune">
              Select any run from the left side to reopen that stored output.
            </p>
          )}
        </section>
      </div>
    </AppShell>
  );
}
