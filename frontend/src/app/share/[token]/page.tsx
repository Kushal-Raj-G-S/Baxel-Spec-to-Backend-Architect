"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

type SharedRun = {
  run_id: string;
  status: string;
  created_at: string;
  project_name?: string | null;
  spec_title?: string | null;
  result?: {
    entities?: Array<{ name: string; fields?: Array<{ name: string; type?: string }> }>;
    endpoints?: Array<{ method: string; path: string; desc?: string }>;
    rules?: Array<string | { name?: string; type?: string; trigger_condition?: string }>;
    migration_sql?: string | string[] | Array<string | string[]>;
  } | null;
};

export default function SharedRunPage({ params }: { params: { token: string } }) {
  const apiBaseUrl = useMemo(
    () => process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000",
    []
  );
  const [data, setData] = useState<SharedRun | null>(null);
  const [status, setStatus] = useState("Loading shared output...");

  useEffect(() => {
    const loadSharedRun = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/runs/share/${params.token}`);
        if (!response.ok) {
          setStatus("Invalid or expired shared link.");
          return;
        }
        const payload = (await response.json()) as SharedRun;
        setData(payload);
        setStatus("");
      } catch {
        setStatus("Unable to load shared output.");
      }
    };

    loadSharedRun();
  }, [apiBaseUrl, params.token]);

  const entities = data?.result?.entities || [];
  const endpoints = data?.result?.endpoints || [];
  const rules = data?.result?.rules || [];
  const sql = data?.result?.migration_sql;
  const sqlText = Array.isArray(sql) ? sql.flat(Infinity as 1).join("\n\n") : String(sql || "");

  return (
    <main className="min-h-screen bg-bone px-5 py-10">
      <div className="mx-auto w-full max-w-5xl space-y-6">
        <header className="rounded-3xl border border-dune/20 bg-white/70 p-6">
          <p className="text-xs uppercase tracking-[0.2em] text-dune">Baxel Shared Output</p>
          <h1 className="mt-2 text-2xl font-semibold text-ink">{data?.project_name || "Shared run"}</h1>
          <p className="mt-1 text-sm text-dune">{data?.spec_title || "Untitled spec"}</p>
          <p className="mt-2 text-xs text-dune">{data?.created_at ? new Date(data.created_at).toLocaleString() : ""}</p>
          <p className="mt-1 text-xs uppercase tracking-[0.16em] text-dune">{data?.status || ""}</p>
          <Link href="/" className="mt-4 inline-block rounded-full border border-dune/30 px-4 py-2 text-xs text-ink">
            Open Baxel
          </Link>
        </header>

        {status ? (
          <section className="rounded-3xl border border-dune/20 bg-white/70 p-6 text-sm text-dune">
            {status}
          </section>
        ) : (
          <>
            <section className="grid gap-6 md:grid-cols-2">
              <div className="rounded-3xl border border-dune/20 bg-white/70 p-6">
                <p className="text-xs uppercase tracking-[0.2em] text-dune">ERD Entities</p>
                <div className="mt-4 space-y-3">
                  {entities.length ? entities.map((entity, index) => (
                    <div key={`${entity.name}-${index}`} className="rounded-2xl border border-dune/20 bg-bone/80 p-3">
                      <p className="text-sm font-semibold text-ink">{entity.name}</p>
                      <div className="mt-1 space-y-1">
                        {(entity.fields || []).map((field, fieldIndex) => (
                          <p key={`${entity.name}-${field.name}-${fieldIndex}`} className="text-xs text-dune">
                            {field.name} {field.type ? `(${field.type})` : ""}
                          </p>
                        ))}
                      </div>
                    </div>
                  )) : <p className="text-xs text-dune">No entities captured.</p>}
                </div>
              </div>

              <div className="rounded-3xl border border-dune/20 bg-white/70 p-6">
                <p className="text-xs uppercase tracking-[0.2em] text-dune">API Endpoints</p>
                <div className="mt-4 space-y-3">
                  {endpoints.length ? endpoints.map((endpoint, index) => (
                    <div key={`${endpoint.method}-${endpoint.path}-${index}`} className="rounded-2xl border border-dune/20 bg-bone/80 p-3">
                      <p className="text-xs font-semibold text-ink">{endpoint.method} {endpoint.path}</p>
                      <p className="mt-1 text-xs text-dune">{endpoint.desc || "Generated endpoint"}</p>
                    </div>
                  )) : <p className="text-xs text-dune">No endpoints captured.</p>}
                </div>
              </div>
            </section>

            <section className="grid gap-6 md:grid-cols-2">
              <div className="rounded-3xl border border-dune/20 bg-white/70 p-6">
                <p className="text-xs uppercase tracking-[0.2em] text-dune">Business Rules</p>
                <div className="mt-4 space-y-2">
                  {rules.length ? rules.map((rule, index) => (
                    <p key={`rule-${index}`} className="rounded-xl border border-dune/20 bg-bone/80 px-3 py-2 text-xs text-ink">
                      {typeof rule === "string" ? rule : `${rule.name || "Rule"}${rule.trigger_condition ? ` - ${rule.trigger_condition}` : ""}`}
                    </p>
                  )) : <p className="text-xs text-dune">No business rules captured.</p>}
                </div>
              </div>

              <div className="rounded-3xl border border-dune/20 bg-white/70 p-6">
                <p className="text-xs uppercase tracking-[0.2em] text-dune">Migration SQL</p>
                <pre className="mt-4 max-h-72 overflow-auto whitespace-pre-wrap text-xs text-ink">
                  {sqlText || "No SQL captured."}
                </pre>
              </div>
            </section>
          </>
        )}
      </div>
    </main>
  );
}
