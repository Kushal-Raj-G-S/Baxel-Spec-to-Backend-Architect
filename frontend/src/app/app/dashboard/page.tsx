"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import AppShell from "../../components/app-shell";
import { supabase } from "../../../lib/supabase-browser";
import { resolveAvatarUrl } from "../../../lib/avatar";

const pipelineStages = [
  "Spec cleanup",
  "Entities & relations",
  "Model proposal",
  "API surface",
  "Business rules",
  "Code skeleton"
];

type PipelineResult = {
  entities?: Array<{
    name: string;
    fields?: Array<{
      name: string;
      type: string;
      constraints?: string[];
    }>;
  }>;
  relationships?: string[];
  join_tables?: Array<{
    name: string;
    left_entity?: string;
    right_entity?: string;
    purpose?: string;
    fields?: string[];
  }>;
  endpoints?: Array<{ method: string; path: string; desc?: string; errors?: string[] }>;
  rules?: Array<string | { name?: string; type?: string; trigger_condition?: string }>;
  code_skeleton?: {
    models?: string;
    routers?: string;
    services?: string;
  };
  migration_sql?: string | string[] | Array<string | string[]>;
};

type DashboardSummary = {
  projects_count: number;
  specs_count: number;
  pipeline_runs_count: number;
  recent_projects: Array<{ id: string; name: string; created_at: string }>;
  recent_pipeline_runs: Array<{
    id: string;
    status: string;
    created_at: string;
    spec_title?: string;
    project_name?: string;
  }>;
};

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
};

const starterTemplates = [
  {
    label: "E-commerce",
    projectName: "ShopFlow",
    specTitle: "E-commerce platform with catalog and orders",
    specContent:
      "Customers browse products, add items to cart, place orders, and track shipments. Admin manages inventory and promotions. Include payments, refunds, and order status timeline."
  },
  {
    label: "SaaS with teams",
    projectName: "TeamOrbit",
    specTitle: "B2B SaaS with org workspaces and roles",
    specContent:
      "Organizations create workspaces, invite members, assign roles, and manage projects. Add usage analytics, audit logs, and tier-based feature access."
  },
  {
    label: "Hospital management",
    projectName: "MediCore",
    specTitle: "Hospital operations and patient records",
    specContent:
      "Manage patient registration, doctors, appointments, ward admissions, prescriptions, and billing. Include role-based access and clinical timeline history."
  },
  {
    label: "Food delivery",
    projectName: "QuickBite",
    specTitle: "Food delivery app with dispatch workflow",
    specContent:
      "Users place food orders, restaurants accept and prepare, delivery agents pick up and deliver. Include real-time order states, tips, and delivery SLA rules."
  },
  {
    label: "Learning platform",
    projectName: "LearnSphere",
    specTitle: "Learning management platform with live classes",
    specContent:
      "Students enroll in courses, watch lessons, attend live classes, submit assignments, and receive grades. Instructors manage curriculum and attendance."
  }
];

export default function DashboardPage() {
  const apiBaseUrl = useMemo(
    () => process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000",
    []
  );
  const [projectName, setProjectName] = useState("");
  const [specTitle, setSpecTitle] = useState("");
  const [specContent, setSpecContent] = useState("");
  const [status, setStatus] = useState("Idle");
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [profileEmail, setProfileEmail] = useState("loading...");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [avatarUploading, setAvatarUploading] = useState(false);
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

  const loadDashboard = async () => {
    try {
      const [{ data: userData }, token] = await Promise.all([supabase.auth.getUser(), getAccessToken()]);

      if (userData.user?.email) {
        setProfileEmail(userData.user.email);
      } else {
        setProfileEmail("Not signed in");
      }

      if (!token) {
        setStatus("Please sign in at /auth to load dashboard");
        return;
      }

      const authHeaders = getAuthHeaders(token);
      const summaryRes = await fetch(`${apiBaseUrl}/dashboard/summary`, { headers: authHeaders });

      if (summaryRes.ok) {
        const data = await summaryRes.json();
        setSummary(data);
      }

      const profileRes = await fetch(`${apiBaseUrl}/profile/me`, { headers: authHeaders });
      if (profileRes.ok) {
        const data = await profileRes.json();
        setProfile(data);
        setAvatarDisplayUrl(await resolveAvatarUrl(data.avatar_url));
      }

      const planRes = await fetch(`${apiBaseUrl}/profile/plan`, { headers: authHeaders });
      if (planRes.ok) {
        const data = await planRes.json();
        setPlan(data);
      }
    } catch (error) {
      setProfileEmail("Profile unavailable");
    }
  };

  useEffect(() => {
    loadDashboard();
  }, []);

  const runPipeline = async () => {
    try {
      setStatus("Creating project...");
      setResult(null);
      const token = await getAccessToken();
      if (!token) {
        setStatus("Please sign in at /auth before running pipeline");
        return;
      }

      const headers = getAuthHeaders(token);

      const projectRes = await fetch(`${apiBaseUrl}/projects`, {
        method: "POST",
        headers,
        body: JSON.stringify({ name: projectName })
      });
      if (!projectRes.ok) {
        throw new Error("Project creation failed");
      }
      const project = await projectRes.json();

      setStatus("Saving spec...");
      const specRes = await fetch(`${apiBaseUrl}/specs`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          project_id: project.id,
          title: specTitle,
          content: specContent
        })
      });
      if (!specRes.ok) {
        throw new Error("Spec creation failed");
      }
      const spec = await specRes.json();

      setStatus("Running pipeline...");
      const pipelineRes = await fetch(`${apiBaseUrl}/pipelines/run`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          project_id: project.id,
          spec_id: spec.id,
          stack: "fastapi+supabase"
        })
      });
      if (!pipelineRes.ok) {
        throw new Error("Pipeline failed");
      }
      const pipeline = await pipelineRes.json();
      setResult(pipeline.result || null);
      setStatus("Completed");
      await loadDashboard();
    } catch (error) {
      setStatus("Error - check backend server");
    }
  };

  const uploadAvatar = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      setAvatarUploading(true);
      const { data: userData } = await supabase.auth.getUser();
      const userId = userData.user?.id;
      if (!userId) {
        setStatus("Sign in first to upload avatar");
        return;
      }

      const token = await getAccessToken();
      if (!token) {
        setStatus("Please sign in at /auth before uploading avatar");
        return;
      }

      const ext = file.name.split(".").pop() || "jpg";
      const path = `${userId}/avatar-${Date.now()}.${ext}`;

      const uploadRes = await supabase.storage.from("avatars").upload(path, file, {
        upsert: true
      });

      if (uploadRes.error) {
        throw uploadRes.error;
      }

      const headers = getAuthHeaders(token);
      const profileRes = await fetch(`${apiBaseUrl}/profile/me`, {
        method: "PATCH",
        headers,
        body: JSON.stringify({ avatar_url: path })
      });

      if (!profileRes.ok) {
        throw new Error("Failed to save profile avatar");
      }

      const data = await profileRes.json();
      setProfile(data);
      setAvatarDisplayUrl(await resolveAvatarUrl(data.avatar_url));
      setStatus("Profile photo updated");
    } catch (error) {
      setStatus("Avatar upload failed. Ensure 'avatars' bucket exists in Supabase.");
    } finally {
      setAvatarUploading(false);
    }
  };

  const endpoints = result?.endpoints || [];
  const rules = result?.rules || [];
  const entities = result?.entities || [];
  const relationships = result?.relationships || [];
  const joinTables = result?.join_tables || [];
  const codeSkeleton = result?.code_skeleton;
  const migrationSql = result?.migration_sql;

  const normalizeSqlText = (value: unknown): string => {
    if (Array.isArray(value)) {
      return value.map((item) => normalizeSqlText(item)).filter(Boolean).join("\n\n");
    }

    const text = String(value || "").trim();
    if (!text) return "";

    const maybeList = text.startsWith("[") && text.endsWith("]");
    if (maybeList) {
      const extractedCreateStatements = text.match(/CREATE\s+TABLE[\s\S]*?(?=(?:CREATE\s+TABLE)|$)/gi);
      if (extractedCreateStatements?.length) {
        return extractedCreateStatements
          .map((statement) => statement.replace(/[\],'"]+$/g, "").trim())
          .join(";\n\n");
      }
    }

    return text.replace(/\\n/g, "\n");
  };

  const migrationSqlText = normalizeSqlText(migrationSql);
  const isStarterLimitReached =
    (plan?.plan_name || "Starter").toLowerCase() === "starter" &&
    (plan?.runs_used_this_month || 0) >= (plan?.monthly_run_limit || 3);

  const downloadTextFile = (filename: string, content: string) => {
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  };

  const exportJson = () => {
    const payload = JSON.stringify(result || {}, null, 2);
    downloadTextFile("baxel-blueprint.json", payload);
  };

  const exportOpenApi = () => {
    const lines = [
      "openapi: 3.0.3",
      "info:",
      "  title: Baxel Generated API",
      "  version: 1.0.0",
      "paths:"
    ];

    (endpoints || []).forEach((endpoint) => {
      const method = endpoint.method.toLowerCase();
      lines.push(`  ${endpoint.path}:`);
      lines.push(`    ${method}:`);
      lines.push(`      summary: ${endpoint.desc || "Generated endpoint"}`);
      lines.push("      responses:");
      lines.push("        '200':");
      lines.push("          description: Success");
      if ((endpoint.errors || []).length) {
        lines.push("      x-domain-errors:");
        (endpoint.errors || []).forEach((errorCode) => {
          lines.push(`        - ${errorCode}`);
        });
      }
    });

    downloadTextFile("baxel-openapi.yaml", lines.join("\n"));
  };

  const exportSql = () => {
    downloadTextFile("baxel-migration.sql", migrationSqlText || "-- No SQL generated yet.");
  };

  const normalizedRules = (rules.length ? rules : [
    "Every entity needs a primary key",
    "Many-to-many requires a join table",
    "Every endpoint includes error shapes"
  ]).map((rule) => {
    if (typeof rule === "string") {
      return { name: rule, type: "rule", trigger_condition: "" };
    }

    return {
      name: rule.name || "Rule",
      type: rule.type || "rule",
      trigger_condition: rule.trigger_condition || ""
    };
  });

  // Fix ISSUE 4: map normalized constraints to compact UI chips for readable schema rows.
  const renderConstraintChip = (constraint: string, index: number) => {
    const normalized = constraint.toLowerCase();
    let label = normalized.toUpperCase();
    if (normalized === "primary_key") label = "KEY PK";
    if (normalized === "foreign_key") label = "LINK FK";
    if (normalized === "not_null") label = "NOT NULL";
    if (normalized === "unique") label = "UNIQUE";
    if (normalized === "default_true") label = "DEFAULT TRUE";
    if (normalized === "default_false") label = "DEFAULT FALSE";

    return (
      <span key={`${constraint}-${index}`} className="rounded-full border border-dune/20 bg-white px-2 py-0.5 text-[10px] uppercase tracking-[0.08em] text-dune">
        {label}
      </span>
    );
  };

  return (
    <AppShell>
      <div className="grid gap-6 lg:grid-cols-[1.4fr_0.6fr]">
        <section className="glass rounded-3xl p-8 reveal">
          <p className="label">Pipeline builder</p>
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            {pipelineStages.map((stage) => (
              <div key={stage} className="rounded-2xl border border-dune/20 bg-white/70 p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-dune">{status}</p>
                <p className="mt-3 text-sm font-medium text-ink">{stage}</p>
              </div>
            ))}
          </div>
          <div className="mt-6 rounded-2xl bg-ink p-4 text-bone">
            <p className="text-xs uppercase tracking-[0.2em]">Live insight</p>
            <p className="mt-3 text-sm">
              {status === "Completed"
                ? "Pipeline complete. Review entities, APIs, and rules below."
                : status}
            </p>
          </div>
        </section>

        <section className="glass rounded-3xl p-8 reveal reveal-delay-1">
          <p className="label">Run a spec</p>
          <div className="mt-4 rounded-2xl border border-dune/20 bg-white/70 p-4">
            <p className="text-[11px] uppercase tracking-[0.2em] text-dune">STARTER TEMPLATES</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {starterTemplates.map((template) => (
                <button
                  key={template.label}
                  className="rounded-full border border-dune/30 px-3 py-1 text-xs text-ink"
                  onClick={() => {
                    setProjectName(template.projectName);
                    setSpecTitle(template.specTitle);
                    setSpecContent(template.specContent);
                  }}
                >
                  {template.label}
                </button>
              ))}
            </div>
          </div>
          <div className="mt-6 space-y-4 text-sm text-dune">
            <div>
              <label className="text-xs uppercase tracking-[0.2em] text-dune">Project name</label>
              <input
                className="mt-2 w-full rounded-2xl border border-dune/20 bg-white/70 px-4 py-3 text-sm"
                value={projectName}
                onChange={(event) => setProjectName(event.target.value)}
                placeholder="Atlas Marketplace"
              />
            </div>
            <div>
              <label className="text-xs uppercase tracking-[0.2em] text-dune">Spec title</label>
              <input
                className="mt-2 w-full rounded-2xl border border-dune/20 bg-white/70 px-4 py-3 text-sm"
                value={specTitle}
                onChange={(event) => setSpecTitle(event.target.value)}
                placeholder="Marketplace spec"
              />
            </div>
            <div>
              <label className="text-xs uppercase tracking-[0.2em] text-dune">Spec content</label>
              <textarea
                className="mt-2 h-32 w-full rounded-2xl border border-dune/20 bg-white/70 px-4 py-3 text-sm"
                value={specContent}
                onChange={(event) => setSpecContent(event.target.value)}
                placeholder="Users can list products, buyers place orders, and admins verify listings."
              />
            </div>
            <button
              className="w-full rounded-full bg-ink px-4 py-3 text-sm text-bone"
              onClick={runPipeline}
            >
              Run pipeline
            </button>
            {isStarterLimitReached ? (
              <p className="rounded-xl border border-amber-300/70 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                You&apos;ve used {plan?.runs_used_this_month || 3}/{plan?.monthly_run_limit || 3} runs this month. Upgrade to Studio for unlimited runs. {" "}
                <Link href="/pricing" className="underline">
                  View pricing
                </Link>
              </p>
            ) : null}
          </div>
        </section>
      </div>

      <section className="mt-6 grid gap-6 md:grid-cols-3">
        {[
          { title: "Projects", value: `${summary?.projects_count ?? 0}` },
          { title: "Specs", value: `${summary?.specs_count ?? 0}` },
          { title: "Pipeline runs", value: `${summary?.pipeline_runs_count ?? 0}` }
        ].map((card) => (
          <div key={card.title} className="glass rounded-3xl p-6 reveal">
            <p className="label">{card.title}</p>
            <p className="mt-3 text-2xl font-semibold text-ink">{card.value}</p>
          </div>
        ))}
      </section>

      <section className="mt-6">
        <div className="glass rounded-3xl p-6 reveal">
          <p className="label">Signed-in profile</p>
          <div className="mt-3 flex items-center gap-4">
            {avatarDisplayUrl ? (
              <img src={avatarDisplayUrl} alt="Profile" className="h-14 w-14 rounded-full object-cover" />
            ) : (
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-ink text-bone">
                {profileEmail.slice(0, 1).toUpperCase()}
              </div>
            )}
            <div>
              <p className="text-lg font-semibold text-ink">{profile?.full_name || profileEmail}</p>
              <p className="text-xs text-dune">@{profile?.username || "set-username"}</p>
            </div>
          </div>
          <div className="mt-4">
            <label className="rounded-full border border-dune/40 px-4 py-2 text-sm cursor-pointer inline-block">
              {avatarUploading ? "Uploading..." : "Upload profile photo"}
              <input type="file" accept="image/*" className="hidden" onChange={uploadAvatar} />
            </label>
          </div>
        </div>
      </section>

      <section className="mt-6 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="glass rounded-3xl p-8 reveal">
          <p className="label">Active projects</p>
          <div className="mt-6 space-y-3">
            {(summary?.recent_projects?.length
              ? summary.recent_projects
              : [{ id: "draft-project", name: projectName, created_at: "" }]).map((project, index) => (
              <div
                key={`${project.id}-${project.name}-${index}`}
                className="flex items-center justify-between rounded-2xl border border-dune/20 bg-white/70 px-4 py-3"
              >
                <span className="text-sm font-medium text-ink">{project.name}</span>
                <span className="text-xs uppercase tracking-[0.2em] text-dune">Review</span>
              </div>
            ))}
          </div>
        </div>
        <div className="glass rounded-3xl p-8 reveal reveal-delay-2">
          <p className="label">ERD canvas</p>
          <div className="mt-6 grid gap-3 md:grid-cols-2">
            {(entities.length
              ? entities
              : [
                  {
                    name: "Project",
                    fields: [
                      { name: "id", type: "uuid", constraints: ["primary_key"] },
                      { name: "name", type: "text", constraints: ["not_null"] },
                      { name: "created_at", type: "timestamptz", constraints: ["not_null"] }
                    ]
                  },
                  {
                    name: "Spec",
                    fields: [
                      { name: "id", type: "uuid", constraints: ["primary_key"] },
                      { name: "project_id", type: "uuid", constraints: ["foreign_key", "not_null"] },
                      { name: "content", type: "text", constraints: ["not_null"] }
                    ]
                  }
                ]
            ).map((entity, index) => (
              <div key={`${entity.name}-${index}`} className="rounded-2xl border border-dune/20 bg-white/70 p-4">
                <p className="text-sm font-semibold text-ink">{entity.name}</p>
                <div className="mt-2 space-y-1">
                  {(entity.fields?.length
                    ? entity.fields
                    : [{ name: "id", type: "uuid", constraints: ["primary_key"] }]
                  ).map((field, fieldIndex) => (
                    <div key={`${entity.name}-${field.name}-${fieldIndex}`} className="flex flex-wrap items-center gap-2 text-xs text-dune">
                      <span className="font-semibold text-ink">{field.name}</span>
                      <span className="rounded-full bg-ink px-2 py-0.5 text-[10px] uppercase tracking-[0.08em] text-bone">
                        {field.type}
                      </span>
                      {(field.constraints || []).map((constraint, constraintIndex) =>
                        renderConstraintChip(constraint, constraintIndex)
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 rounded-2xl border border-dune/20 bg-white/70 p-4">
            <p className="text-xs uppercase tracking-[0.2em] text-dune">Relationships</p>
            {relationships.length ? (
              <div className="mt-2 space-y-1">
                {relationships.map((item, index) => (
                  <p key={`${item}-${index}`} className="text-xs text-dune">
                    {item}
                  </p>
                ))}
              </div>
            ) : (
              <p className="mt-2 text-xs text-dune">No relationships identified.</p>
            )}
          </div>
        </div>
      </section>

      <section className="mt-6">
        <div className="glass rounded-3xl p-8 reveal">
          <p className="label">Join tables</p>
          <div className="mt-4 space-y-3">
            {joinTables.length ? joinTables.map((table, index) => (
              <div key={`${table.name}-${index}`} className="rounded-2xl border border-dune/20 bg-white/70 p-4">
                <p className="text-sm font-semibold text-ink">{table.name}</p>
                <p className="mt-1 text-xs text-dune">
                  {table.left_entity} <span className="mx-1">&lt;-&gt;</span> {table.right_entity}
                </p>
                <p className="mt-1 text-xs text-dune">{table.purpose}</p>
                <div className="mt-2 space-y-1">
                  {(table.fields || []).map((field, fieldIndex) => (
                    <p key={`${table.name}-${field}-${fieldIndex}`} className="text-xs text-dune">
                      {field}
                    </p>
                  ))}
                </div>
              </div>
            )) : <p className="text-xs text-dune">No join tables required.</p>}
          </div>
        </div>
      </section>

      <section className="mt-6 grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="glass rounded-3xl p-8 reveal">
          <p className="label">Business rules</p>
          <div className="mt-6 space-y-3">
            {normalizedRules.map((rule, index) => (
              <div key={`${rule.name}-${index}`} className="rounded-2xl border border-dune/20 bg-white/70 p-4">
                <p className="text-sm font-semibold text-ink">{rule.name}</p>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-dune">
                  <span className="rounded-full border border-dune/20 bg-white px-2 py-0.5 uppercase tracking-[0.08em]">
                    {rule.type}
                  </span>
                  {rule.trigger_condition && (
                    <span className="rounded-full border border-dune/20 bg-white px-2 py-0.5">
                      Trigger: {rule.trigger_condition}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="glass rounded-3xl p-8 reveal reveal-delay-1">
          <p className="label">API surface</p>
          <div className="mt-6 space-y-3">
            {(endpoints.length ? endpoints : [
              { method: "POST", path: "/projects", desc: "Create a project" },
              { method: "POST", path: "/specs", desc: "Upload new PRD" },
              { method: "GET", path: "/projects/{id}", desc: "Project summary" },
              { method: "POST", path: "/pipelines/run", desc: "Run pipeline" }
            ]).map((api, index) => (
              <div key={`${api.method}-${api.path}-${index}`} className="rounded-2xl border border-dune/20 bg-white/70 p-4">
                <div className="flex items-center gap-3">
                  <span className="code-pill">{api.method}</span>
                  <span className="text-sm font-medium text-ink">{api.path}</span>
                </div>
                <p className="mt-2 text-xs text-dune">{api.desc}</p>
                {!!api.errors?.length && (
                  <p className="mt-1 text-[11px] text-dune/90">Errors: {api.errors.join(" | ")}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="glass rounded-3xl p-8 reveal">
          <p className="label">Code skeleton</p>
          <div className="mt-4 space-y-3">
            <div className="rounded-2xl border border-dune/20 bg-white/70 p-4">
              <p className="text-xs uppercase tracking-[0.2em] text-dune">Models</p>
              <pre className="mt-2 whitespace-pre-wrap text-xs text-ink">{codeSkeleton?.models || "No models generated yet."}</pre>
            </div>
            <div className="rounded-2xl border border-dune/20 bg-white/70 p-4">
              <p className="text-xs uppercase tracking-[0.2em] text-dune">Routers</p>
              <pre className="mt-2 whitespace-pre-wrap text-xs text-ink">{codeSkeleton?.routers || "No routers generated yet."}</pre>
            </div>
            <div className="rounded-2xl border border-dune/20 bg-white/70 p-4">
              <p className="text-xs uppercase tracking-[0.2em] text-dune">Services</p>
              <pre className="mt-2 whitespace-pre-wrap text-xs text-ink">{codeSkeleton?.services || "No services generated yet."}</pre>
            </div>
          </div>
        </div>

        <div className="glass rounded-3xl p-8 reveal reveal-delay-1">
          <p className="label">Migration SQL</p>
          <div className="mt-4 rounded-2xl border border-dune/20 bg-white/70 p-4">
            <pre className="whitespace-pre-wrap text-xs text-ink">{migrationSqlText || "No SQL migration generated yet."}</pre>
          </div>
        </div>
      </section>

      <section className="mt-6">
        <div className="glass rounded-3xl p-6 reveal">
          <p className="label">Exports</p>
          <div className="mt-4 flex flex-wrap gap-3">
            <button className="rounded-full bg-ink px-4 py-2 text-sm text-bone" onClick={exportJson}>
              Export JSON
            </button>
            <button className="rounded-full border border-dune/40 px-4 py-2 text-sm" onClick={exportOpenApi}>
              Export OpenAPI YAML
            </button>
            <button className="rounded-full border border-dune/40 px-4 py-2 text-sm" onClick={exportSql}>
              Export SQL
            </button>
          </div>
        </div>
      </section>

      <section className="mt-6">
        <div className="glass rounded-3xl p-8 reveal">
          <p className="label">Recent pipeline runs</p>
          <div className="mt-6 space-y-3">
            {(summary?.recent_pipeline_runs?.length
              ? summary.recent_pipeline_runs
              : [{ id: "N/A", status: "No runs yet", created_at: "" }]
            ).map((run) => (
              <div
                key={run.id}
                className="flex items-center justify-between rounded-2xl border border-dune/20 bg-white/70 px-4 py-3"
              >
                <div>
                  <p className="text-sm font-medium text-ink">{run.spec_title || run.id}</p>
                  <p className="text-xs text-dune">
                    {run.project_name ? `${run.project_name} • ` : ""}
                    {run.created_at ? new Date(run.created_at).toLocaleString() : ""}
                  </p>
                </div>
                <span className="text-xs uppercase tracking-[0.2em] text-dune">{run.status}</span>
              </div>
            ))}
          </div>
        </div>
      </section>
    </AppShell>
  );
}
