"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import AppShell from "../../components/app-shell";
import { supabase } from "../../../lib/supabase-browser";
import { resolveAvatarUrl } from "../../../lib/avatar";

const pipelineStages = [
  "Spec expansion",
  "Spec cleanup",
  "Entities & relations",
  "Model proposal",
  "API surface",
  "Business rules",
  "Code skeleton"
] as const;

const stageIcons: Record<(typeof pipelineStages)[number], string> = {
  "Spec expansion": "SE",
  "Spec cleanup": "SC",
  "Entities & relations": "ER",
  "Model proposal": "MP",
  "API surface": "AP",
  "Business rules": "BR",
  "Code skeleton": "</>"
};

type PipelineResult = {
  summary?: { summary?: string } | string;
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
  __meta?: {
    source?: string;
    model?: string;
    spec_expansion?: {
      source?: string;
      model?: string;
      original_chars?: number;
      expanded_chars?: number;
      inferred_count?: number;
    };
  };
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
  plan_code?: string;
  plan_name: string;
  status: string;
  monthly_run_limit: number;
  runs_used_this_month: number;
  monthly_project_limit: number;
  projects_used_this_month: number;
  runs_per_project_limit?: number;
  idea_char_limit?: number;
};

type PreferenceRole = "solo_dev" | "founder" | "backend_engineer" | "student";
type PreferenceIntent = "new_build" | "prototype" | "document" | "explore";
type PreferenceExperience = "beginner" | "intermediate" | "advanced";
type PreferenceHeardAbout = "linkedin" | "product_hunt" | "google" | "other";

type UserPreferenceRow = {
  user_id: string;
  role?: PreferenceRole;
  intent?: PreferenceIntent;
  experience: PreferenceExperience;
  heard_about?: PreferenceHeardAbout;
  heard_about_other?: string | null;
};

type ViewMode = "guide" | "builder" | "pro";
type OutputTab = "schema" | "api" | "code" | "sql" | "rules";

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

const starterLockedPreviewMessages = [
  "Advanced logic map, SQL migration strategy, and code skeleton are ready internally. Upgrade to reveal full artifact depth and exports.",
  "Hidden output contains deeper validation paths, relational edge handling, and export-ready artifacts. Upgrade to unlock the full pack.",
  "Your backend draft already includes richer SQL and implementation scaffolds behind this view. Upgrade to access complete outputs.",
  "Internal generation has additional architecture layers and advanced rule wiring. Upgrade to reveal all production artifacts.",
  "This run includes extended schema intelligence and deployment-grade blueprints under the hood. Upgrade to open the complete output set."
];

const fallbackEntities = [
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
];

export default function DashboardPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const apiBaseUrl = useMemo(
    () => process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000",
    []
  );

  const [projectName, setProjectName] = useState("");
  const [ideaName, setIdeaName] = useState("");
  const [specTitle, setSpecTitle] = useState("");
  const [specContent, setSpecContent] = useState("");
  const [status, setStatus] = useState("Idle");
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [lastRunMeta, setLastRunMeta] = useState<{ projectName: string; specTitle: string; runId?: string } | null>(null);
  const [generationMeta, setGenerationMeta] = useState<{ source?: string; model?: string } | null>(null);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [profileEmail, setProfileEmail] = useState("loading...");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [avatarUploading, setAvatarUploading] = useState(false);
  const [avatarDisplayUrl, setAvatarDisplayUrl] = useState<string | null>(null);
  const [plan, setPlan] = useState<PlanSummary | null>(null);
  const [isPlanLoading, setIsPlanLoading] = useState(true);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [viewMode, setViewMode] = useState<ViewMode>("builder");
  const [userPreference, setUserPreference] = useState<UserPreferenceRow | null>(null);
  const [showGenerationDetails, setShowGenerationDetails] = useState(false);
  const [activeTab, setActiveTab] = useState<OutputTab>("schema");
  const [hasCheckedPreferences, setHasCheckedPreferences] = useState(false);
  const [starterLockedPreviewIndex, setStarterLockedPreviewIndex] = useState(0);
  const summaryRef = useRef<HTMLDivElement | null>(null);

  const viewModeStorageKey = "baxel:view-mode";
  const planSummaryStorageKey = "baxel:plan-summary";

  const deriveViewMode = (preference: UserPreferenceRow | null): ViewMode => {
    if (!preference) return "builder";
    if (preference.experience === "beginner") return "guide";
    if (preference.experience === "advanced") return "pro";
    return "builder";
  };

  const getAccessToken = async () => {
    const { data } = await supabase.auth.getSession();
    return data.session?.access_token || null;
  };

  const getAuthHeaders = (token: string) => ({
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`
  });

  const loadDashboard = useCallback(async () => {
    setIsPlanLoading(true);
    try {
      const [{ data: userData }, token] = await Promise.all([supabase.auth.getUser(), getAccessToken()]);
      setProfileEmail(userData.user?.email || "Not signed in");
      const userId = userData.user?.id;
      if (!token) {
        setStatus("Please sign in at /auth to load dashboard");
        setHasCheckedPreferences(true);
        setIsPlanLoading(false);
        return;
      }
      if (!userId) {
        setStatus("Please sign in at /auth to load dashboard");
        setHasCheckedPreferences(true);
        setIsPlanLoading(false);
        return;
      }

      const { data: preferenceData, error: preferenceError } = await supabase
        .from("user_preferences")
        .select("user_id, role, intent, experience, heard_about, heard_about_other")
        .eq("user_id", userId)
        .maybeSingle();

      if (!preferenceError && !preferenceData) {
        router.replace("/onboarding");
        return;
      }

      const derivedMode = deriveViewMode(preferenceData as UserPreferenceRow | null);
      const storedMode = typeof window !== "undefined" ? localStorage.getItem(viewModeStorageKey) : null;
      const nextMode: ViewMode = storedMode === "guide" || storedMode === "builder" || storedMode === "pro" ? storedMode : derivedMode;
      setUserPreference((preferenceData as UserPreferenceRow | null) || null);
      setViewMode(nextMode);
      console.log(`View mode set to: ${nextMode} based on experience: ${preferenceData?.experience || "unknown"}`);
      setHasCheckedPreferences(true);

      const headers = getAuthHeaders(token);
      const [summaryRes, profileRes, planRes] = await Promise.all([
        fetch(`${apiBaseUrl}/dashboard/summary`, { headers, cache: "no-store" }),
        fetch(`${apiBaseUrl}/profile/me`, { headers, cache: "no-store" }),
        fetch(`${apiBaseUrl}/profile/plan?t=${Date.now()}`, { headers, cache: "no-store" })
      ]);

      if (summaryRes.ok) setSummary(await summaryRes.json());
      if (profileRes.ok) {
        const profileData = await profileRes.json();
        setProfile(profileData);
        setAvatarDisplayUrl(await resolveAvatarUrl(profileData.avatar_url));
      }
      if (planRes.ok) {
        const planPayload = await planRes.json();
        setPlan(planPayload);
        if (typeof window !== "undefined") {
          window.localStorage.setItem(planSummaryStorageKey, JSON.stringify(planPayload));
        }
      }
    } catch {
      setProfileEmail("Profile unavailable");
      setHasCheckedPreferences(true);
    } finally {
      setIsPlanLoading(false);
    }
  }, [apiBaseUrl, router]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const rawPlan = window.localStorage.getItem(planSummaryStorageKey);
      if (!rawPlan) return;
      const parsed = JSON.parse(rawPlan) as PlanSummary;
      if (parsed?.plan_code || parsed?.plan_name) {
        setPlan(parsed);
      }
    } catch {
      // Ignore malformed local cache and continue with API data.
    }
  }, []);

  useEffect(() => {
    loadDashboard();

    const onWindowFocus = () => {
      loadDashboard();
    };

    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        loadDashboard();
      }
    };

    window.addEventListener("focus", onWindowFocus);
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      window.removeEventListener("focus", onWindowFocus);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [loadDashboard]);

  const runPipeline = async () => {
    try {
      const trimmedSpec = specContent.trim();
      if (!trimmedSpec) {
        setStatus("Add a short product description first.");
        return;
      }

      if (isPlanLoading && !plan) {
        setStatus("Loading plan details. Try again in a moment.");
        return;
      }

      const planCode = (plan?.plan_code || "starter").toLowerCase();
      const charLimitMap: Record<string, number> = {
        starter: 1000,
        creator: 1500,
        studio: 3000,
        growth: 9000,
        enterprise: 15000,
      };
      const activeCharLimit = plan?.idea_char_limit || charLimitMap[planCode] || 1000;
      if (trimmedSpec.length > activeCharLimit) {
        setStatus(`Idea is too long for ${plan?.plan_name || "Starter"}. Max ${activeCharLimit} characters.`);
        return;
      }

      const inferredTitle = trimmedSpec
        .split(/\n|\./)
        .map((line) => line.trim())
        .find(Boolean)
        ?.slice(0, 68) || "Generated backend spec";
      const fallbackProject = inferredTitle.split(" ").slice(0, 3).join(" ") || "New Project";
      const formalIdeaName = ideaName.trim();
      const finalProjectName = projectName.trim() || formalIdeaName || fallbackProject;
      const finalSpecTitle = formalIdeaName || specTitle.trim() || inferredTitle;

      setResult(null);
      setElapsedSeconds(0);
      setActiveTab("schema");
      setStatus("Creating project...");
      setProjectName(finalProjectName);
      setSpecTitle(finalSpecTitle);
      const token = await getAccessToken();
      if (!token) {
        setStatus("Please sign in at /auth before running pipeline");
        return;
      }

      const headers = getAuthHeaders(token);
      const projectRes = await fetch(`${apiBaseUrl}/projects`, {
        method: "POST",
        headers,
        body: JSON.stringify({ name: finalProjectName })
      });
      if (!projectRes.ok) {
        const detail = await projectRes.text();
        throw new Error(detail || "Project creation failed");
      }
      const project = await projectRes.json();

      setStatus("Saving spec...");
      const onboardingPrefix = userPreference
        ? `[User context]\nRole: ${userPreference.role || "unknown"}\nIntent: ${userPreference.intent || "unknown"}\nExperience: ${userPreference.experience || "unknown"}\nSource: ${userPreference.heard_about === "other" ? (userPreference.heard_about_other || "other") : (userPreference.heard_about || "unknown")}\nAdjust output detail and naming clarity accordingly.`
        : "";
      const intelligenceGuardPrefix = "[System behavior]\nApply full intelligence and complete reasoning depth regardless of plan tier. Plan only affects output visibility and export controls, not inference quality.";
      const formalNamePrefix = formalIdeaName ? `[Idea name]\n${formalIdeaName}` : "";
      const payloadPreamble = [intelligenceGuardPrefix, formalNamePrefix, onboardingPrefix].filter(Boolean).join("\n\n");
      const specPayloadContent = payloadPreamble ? `${payloadPreamble}\n\n[Product spec]\n${specContent}` : specContent;
      const specRes = await fetch(`${apiBaseUrl}/specs`, {
        method: "POST",
        headers,
        body: JSON.stringify({ project_id: project.id, title: finalSpecTitle, content: specPayloadContent })
      });
      if (!specRes.ok) {
        const detail = await specRes.text();
        throw new Error(detail || "Spec creation failed");
      }
      const spec = await specRes.json();

      setStatus("Running pipeline...");
      const pipelineRes = await fetch(`${apiBaseUrl}/pipelines/run`, {
        method: "POST",
        headers,
        body: JSON.stringify({ project_id: project.id, spec_id: spec.id, stack: "fastapi+supabase" })
      });
      if (!pipelineRes.ok) {
        const detail = await pipelineRes.text();
        throw new Error(detail || "Pipeline failed");
      }

      const pipeline = await pipelineRes.json();
      setResult(pipeline.result || null);
      setLastRunMeta({ projectName: finalProjectName, specTitle: finalSpecTitle, runId: pipeline.id });
      setGenerationMeta({
        source: pipelineRes.headers.get("x-baxel-generation-source") || pipeline?.result?.__meta?.source,
        model: pipelineRes.headers.get("x-baxel-generation-model") || pipeline?.result?.__meta?.model,
      });
      setStatus("Completed");
      await loadDashboard();
    } catch (error) {
      const message = String((error as Error)?.message || "").toLowerCase();
      if (message.includes("per-project pipeline limit reached")) {
        setStatus("This project already used all pipeline runs for your current plan. Use another project or upgrade.");
        await loadDashboard();
        return;
      }
      if (message.includes("plan limit reached") || message.includes("upgrade required") || message.includes("402")) {
        setStatus("Plan limit reached. Upgrade to continue.");
        await loadDashboard();
        return;
      }
      setStatus("Error - check backend server");
    }
  };

  const rerunLatest = async () => {
    if (!specContent.trim()) {
      setStatus("Paste spec content to re-run quickly.");
      return;
    }
    await runPipeline();
  };

  const copyShareLinkFromLatest = async () => {
    const targetRunId = lastRunMeta?.runId || summary?.recent_pipeline_runs?.[0]?.id;
    if (!targetRunId) return;

    try {
      const token = await getAccessToken();
      if (!token) return;
      const response = await fetch(`${apiBaseUrl}/runs/${targetRunId}/share`, { headers: getAuthHeaders(token) });
      if (!response.ok) return;
      const payload = await response.json();
      await navigator.clipboard.writeText(`${window.location.origin}/share/${payload.token}`);
      setStatus("Share link copied");
    } catch {
      setStatus("Could not copy share link");
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
      const uploadRes = await supabase.storage.from("avatars").upload(path, file, { upsert: true });
      if (uploadRes.error) throw uploadRes.error;

      const profileRes = await fetch(`${apiBaseUrl}/profile/me`, {
        method: "PATCH",
        headers: getAuthHeaders(token),
        body: JSON.stringify({ avatar_url: path })
      });
      if (!profileRes.ok) throw new Error("Failed to save profile avatar");

      const data = await profileRes.json();
      setProfile(data);
      setAvatarDisplayUrl(await resolveAvatarUrl(data.avatar_url));
      setStatus("Profile photo updated");
    } catch {
      setStatus("Avatar upload failed. Ensure 'avatars' bucket exists in Supabase.");
    } finally {
      setAvatarUploading(false);
    }
  };

  const entities = result?.entities || [];
  const endpoints = result?.endpoints || [];
  const rules = result?.rules || [];
  const relationships = result?.relationships || [];
  const joinTables = result?.join_tables || [];
  const codeSkeleton = result?.code_skeleton;

  const normalizeSqlText = (value: unknown): string => {
    if (Array.isArray(value)) {
      return value.map((item) => normalizeSqlText(item)).filter(Boolean).join("\n\n");
    }

    const text = String(value || "").trim();
    if (!text) return "";
    const maybeList = text.startsWith("[") && text.endsWith("]");
    if (maybeList) {
      const extracted = text.match(/CREATE\s+TABLE[\s\S]*?(?=(?:CREATE\s+TABLE)|$)/gi);
      if (extracted?.length) return extracted.map((item) => item.replace(/[\],'\"]+$/g, "").trim()).join(";\n\n");
    }
    return text.replace(/\\n/g, "\n");
  };

  const migrationSqlText = normalizeSqlText(result?.migration_sql);
  const generatedSummaryText =
    typeof result?.summary === "string"
      ? result.summary
      : result?.summary?.summary || "Baxel translated your spec into a data model, API surface, and implementation scaffold.";
  const normalizedRules = (rules.length ? rules : [
    "Every entity needs a primary key",
    "Many-to-many requires a join table",
    "Every endpoint includes error shapes"
  ]).map((rule) => {
    if (typeof rule === "string") return { name: rule, type: "rule", trigger_condition: "" };
    return { name: rule.name || "Rule", type: rule.type || "rule", trigger_condition: rule.trigger_condition || "" };
  });

  const isCompletedRun = status === "Completed" && !!result;
  const isRunning = ["Creating project...", "Saving spec...", "Running pipeline..."].includes(status);
  const isIdle = !isRunning && !isCompletedRun;

  useEffect(() => {
    if (!isRunning) return;
    const timer = window.setInterval(() => setElapsedSeconds((prev) => prev + 1), 1000);
    return () => window.clearInterval(timer);
  }, [isRunning]);

  useEffect(() => {
    if (!isCompletedRun) return;
    summaryRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [isCompletedRun, result]);

  const processStageIndex = isCompletedRun
    ? pipelineStages.length - 1
    : isRunning
      ? Math.min(Math.floor(elapsedSeconds / 4), pipelineStages.length - 1)
      : -1;
  const progressPercent = isCompletedRun
    ? 100
    : isRunning
      ? Math.max(8, Math.round(((processStageIndex + 1) / pipelineStages.length) * 100))
      : 0;
  const currentStageLabel = isCompletedRun ? "Ready" : pipelineStages[Math.max(processStageIndex, 0)] || "Waiting";

  const formatElapsed = (seconds: number) => `${seconds}s elapsed`;
  const expansionMeta = result?.__meta?.spec_expansion;
  const expandedCharDelta = Math.max(0, (expansionMeta?.expanded_chars || 0) - (expansionMeta?.original_chars || 0));
  const inferredBoostCount = Math.max(0, expansionMeta?.inferred_count || 0);

  const stageInsights: Record<string, string> = {
    "Spec expansion": isCompletedRun
      ? `Expanded idea context by +${expandedCharDelta} chars (${expansionMeta?.source || "none"})`
      : "Internal expansion pending",
    "Spec cleanup": isCompletedRun ? `Normalized: ${(specTitle || "backend spec").slice(0, 54)}` : "Schema normalized and ready",
    "Entities & relations": isCompletedRun ? `Found ${entities.length} entities, ${relationships.length} relationships` : "Entity extraction pending",
    "Model proposal": isCompletedRun ? `Proposed schema: ${entities.length} tables, ${joinTables.length} join tables` : "Schema proposal pending",
    "API surface": isCompletedRun ? `Generated ${endpoints.length} endpoints across resources` : "Endpoint generation pending",
    "Business rules": isCompletedRun ? `Captured ${normalizedRules.length} business rules` : "Rule extraction pending",
    "Code skeleton": isCompletedRun ? `Skeleton ready: ${entities.length} models, ${entities.length} routers, ${entities.length} services` : "Skeleton generation pending"
  };

  const endpointByEntity = entities
    .map((entity) => {
      const count = endpoints.filter((endpoint) => endpoint.path.toLowerCase().includes(entity.name.toLowerCase())).length;
      return { entity: entity.name, count };
    })
    .sort((a, b) => b.count - a.count);

  const topEndpointEntity = endpointByEntity.find((item) => item.count > 0);
  const triggerCount = normalizedRules.filter((rule) => !!rule.trigger_condition).length;

  const keyEntities = entities.slice(0, 5).map((entity) => entity.name);
  const keyEntitiesMore = Math.max(0, entities.length - keyEntities.length);

  const entityRelationCount: Record<string, number> = {};
  entities.forEach((entity) => {
    const lowered = entity.name.toLowerCase();
    entityRelationCount[entity.name] = relationships.filter((line) => line.toLowerCase().includes(lowered)).length;
  });
  const sortedEntities = [...(entities.length ? entities : fallbackEntities)].sort(
    (a, b) => (entityRelationCount[b.name] || 0) - (entityRelationCount[a.name] || 0)
  );
  const highlightedEntities = new Set(sortedEntities.slice(0, 2).map((entity) => entity.name));

  const migrationTableCount = (migrationSqlText.match(/create\s+table/gi) || []).length;

  const runLimitReached = plan
    ? (plan.runs_used_this_month || 0) >= (plan.monthly_run_limit || 0)
    : false;
  const projectLimitReached = plan
    ? (plan.projects_used_this_month || 0) >= (plan.monthly_project_limit || 0)
    : false;
  const isPlanLimitReached = runLimitReached || projectLimitReached;
  const isGenerateBlocked = runLimitReached || (isPlanLoading && !plan);
  const isRerunBlocked = runLimitReached;
  const planUsageText = plan
    ? `Projects ${plan.projects_used_this_month}/${plan.monthly_project_limit} · Runs ${plan.runs_used_this_month}/${plan.monthly_run_limit}`
    : "Usage unavailable";
  const approxRunsPerProject = plan && plan.monthly_project_limit > 0
    ? Math.floor(plan.monthly_run_limit / plan.monthly_project_limit)
    : 0;
  const perProjectRunsAllowed = Math.max(1, plan?.runs_per_project_limit || approxRunsPerProject || 1);
  const activeIdeaCharLimit = plan?.idea_char_limit || 1000;
  const ideaCharsUsed = specContent.length;
  const ideaCharsRemaining = Math.max(0, activeIdeaCharLimit - ideaCharsUsed);

  const isGuideMode = viewMode === "guide";
  const isProMode = viewMode === "pro";

  const currentPlanCode = (plan?.plan_code || "").toLowerCase();
  const tabEntitlements: Record<string, OutputTab[]> = {
    starter: ["schema", "api"],
    creator: ["schema", "api", "sql", "rules"],
    studio: ["schema", "api", "code", "sql", "rules"],
    growth: ["schema", "api", "code", "sql", "rules"],
    enterprise: ["schema", "api", "code", "sql", "rules"],
  };
  const allTabs: OutputTab[] = ["schema", "api", "code", "sql", "rules"];
  const allowedTabs = currentPlanCode
    ? (tabEntitlements[currentPlanCode] || tabEntitlements.starter)
    : allTabs;
  const lockedTabs = currentPlanCode ? allTabs.filter((tab) => !allowedTabs.includes(tab)) : [];
  const isTabAllowed = (tab: OutputTab) => allowedTabs.includes(tab);
  const showStarterLockedPreview = currentPlanCode === "starter" && lockedTabs.length > 0;
  const starterLockedPreviewMessage = starterLockedPreviewMessages[starterLockedPreviewIndex] || starterLockedPreviewMessages[0];

  useEffect(() => {
    if (!showStarterLockedPreview) return;
    const storageKey = "baxel:starter-locked-preview-index";
    const raw = typeof window !== "undefined" ? window.localStorage.getItem(storageKey) : null;
    const parsed = raw ? Number.parseInt(raw, 10) : -1;
    const previousIndex = Number.isFinite(parsed) ? Math.max(-1, Math.min(parsed, starterLockedPreviewMessages.length - 1)) : -1;

    let nextIndex = Math.floor(Math.random() * starterLockedPreviewMessages.length);
    if (starterLockedPreviewMessages.length > 1 && nextIndex === previousIndex) {
      nextIndex = (nextIndex + 1) % starterLockedPreviewMessages.length;
    }

    setStarterLockedPreviewIndex(nextIndex);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(storageKey, String(nextIndex));
    }
  }, [showStarterLockedPreview, lastRunMeta?.runId]);

  useEffect(() => {
    if (!isTabAllowed(activeTab)) {
      setActiveTab(allowedTabs[0]);
    }
  }, [activeTab, currentPlanCode]);

  useEffect(() => {
    const runId = searchParams.get("run");
    if (!runId) return;

    const hydrateRunFromHistory = async () => {
      try {
        const token = await getAccessToken();
        if (!token) return;

        const runRes = await fetch(`${apiBaseUrl}/pipelines/${runId}`, { headers: getAuthHeaders(token) });
        if (!runRes.ok) return;
        const runPayload = await runRes.json();

        setResult(runPayload.result || null);
        setStatus("Completed");
        setActiveTab("schema");
        setElapsedSeconds(0);

        const fallbackProject = searchParams.get("project") || "Saved project";
        const fallbackSpec = searchParams.get("spec") || "Saved spec";
        setLastRunMeta({ projectName: fallbackProject, specTitle: fallbackSpec, runId });

        const resultMeta = runPayload?.result?.__meta || {};
        setGenerationMeta({ source: resultMeta.source, model: resultMeta.model });
      } catch {
        setStatus("Unable to open this saved output.");
      }
    };

    hydrateRunFromHistory();
  }, [searchParams, apiBaseUrl]);

  const setAndPersistViewMode = (mode: ViewMode) => {
    setViewMode(mode);
    localStorage.setItem(viewModeStorageKey, mode);
  };

  const renderSectionBadge = (count: number, label: string) => {
    if (!isProMode) return null;
    return <span className="rounded-full border border-dune/30 bg-white px-2 py-0.5 text-[11px] text-dune">{count} {label}</span>;
  };

  const renderConstraintChip = (constraint: string, index: number) => {
    const normalized = constraint.toLowerCase();
    let label = normalized.toUpperCase();
    if (normalized === "primary_key") label = "KEY PK";
    if (normalized === "foreign_key") label = "LINK FK";
    if (normalized === "not_null") label = "NOT NULL";
    if (normalized === "unique") label = "UNIQUE";
    return (
      <span
        key={`${constraint}-${index}`}
        title={label}
        className="max-w-full break-all rounded-full border border-dune/20 bg-white px-2 py-0.5 text-[10px] uppercase tracking-[0.08em] text-dune"
      >
        {label}
      </span>
    );
  };

  const downloadTextFile = (filename: string, content: string) => {
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  };

  if (!hasCheckedPreferences) {
    return (
      <AppShell>
        <div className="glass rounded-3xl p-8">
          <p className="label">Workspace</p>
          <p className="mt-3 text-sm text-dune">Loading your preferences...</p>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="grid gap-6 lg:grid-cols-[1.35fr_0.65fr]">
        <main className="space-y-6">
          <section className="glass rounded-3xl p-8 reveal">
            <p className="text-sm uppercase tracking-[0.22em] text-dune">Generation status</p>
            <div className="mt-4 rounded-2xl border border-dune/20 bg-white/80 p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-lg font-medium text-ink">
                  {isCompletedRun
                    ? "Backend generated successfully"
                    : isRunning
                      ? `Generating your backend... (${currentStageLabel})`
                      : "Ready when you are"}
                </p>
                {isCompletedRun ? (
                  <span className="rounded-full border border-mint/40 bg-mint/20 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-ink">
                    Ready
                  </span>
                ) : null}
              </div>

              <div className="mt-4 h-3 w-full overflow-hidden rounded-full bg-bone">
                <div
                  className={`h-full rounded-full bg-ink transition-all duration-700 ${isRunning ? "animate-pulse" : ""}`}
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
              <p className="mt-2 text-xs text-dune">
                [{"█".repeat(Math.round(progressPercent / 8)).padEnd(12, "░")}] {isCompletedRun ? "Completed" : `${progressPercent}% in progress`}
                {isRunning ? ` - ${formatElapsed(elapsedSeconds)}` : ""}
              </p>
              {isCompletedRun && generationMeta?.source ? (
                <p className="mt-2 text-xs text-dune">
                  Generated by {generationMeta.source}{generationMeta.model ? ` (${generationMeta.model})` : ""}
                </p>
              ) : null}
            </div>

            <details className="mt-5 rounded-2xl border border-dune/20 bg-white/70 p-4" open={showGenerationDetails}>
              <summary
                className="cursor-pointer text-sm font-semibold text-ink"
                onClick={(event) => {
                  event.preventDefault();
                  setShowGenerationDetails((prev) => !prev);
                }}
              >
                {showGenerationDetails ? "Hide generation details" : "View generation details"}
              </summary>
              {showGenerationDetails ? (
                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  {pipelineStages.map((stage, index) => {
                    const isStageDone = isCompletedRun || (isRunning && index < processStageIndex);
                    const isStageActive = isRunning && index === processStageIndex;
                    return (
                      <div key={stage} className="rounded-xl border border-dune/20 bg-white px-3 py-2">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-dune">{stageIcons[stage]}</p>
                          <p className="text-[11px] text-dune">{isStageDone ? "Completed" : isStageActive ? "Running" : "Queued"}</p>
                        </div>
                        <p className="mt-1 text-sm text-ink">{stage}</p>
                        <p className="mt-1 text-xs text-dune">{stageInsights[stage]}</p>
                      </div>
                    );
                  })}
                </div>
              ) : null}
            </details>
          </section>

          {isCompletedRun ? (
            <div className="space-y-8">
              <section ref={summaryRef} className="rounded-3xl border border-dune/20 bg-white p-8 shadow-[0_24px_60px_rgba(15,15,15,0.12)]">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-dune">Baxel understood your spec</p>
                    <h2 className="mt-2 text-3xl font-semibold text-ink">{lastRunMeta?.projectName || projectName || "Untitled project"}</h2>
                    <p className="mt-2 text-sm text-dune">{generatedSummaryText}</p>
                  </div>
                  <div className="rounded-2xl border border-dune/20 bg-bone/70 px-4 py-3 text-right">
                    <p className="text-lg font-semibold text-ink">{entities.length} entities, {endpoints.length} endpoints</p>
                    <p className="text-xs text-dune">{joinTables.length} joins, {normalizedRules.length} rules, {triggerCount} triggers</p>
                  </div>
                </div>

                <div className="mt-5 flex flex-wrap gap-2">
                  {keyEntities.map((entity) => (
                    <span key={entity} className="rounded-full border border-dune/30 bg-bone px-3 py-1 text-xs font-medium text-ink">{entity}</span>
                  ))}
                  {keyEntitiesMore > 0 ? <span className="rounded-full border border-dune/30 bg-white px-3 py-1 text-xs text-dune">+{keyEntitiesMore} more</span> : null}
                </div>

                <div className="mt-6 rounded-2xl border border-dune/20 bg-bone/50 p-4">
                  <p className="text-xs uppercase tracking-[0.2em] text-dune">Relationship map</p>
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    {sortedEntities.slice(0, 6).map((entity, index) => (
                      <div key={`${entity.name}-${index}`} className="rounded-xl border border-dune/20 bg-white px-3 py-3">
                        <p className="text-sm font-semibold text-ink">{entity.name}</p>
                        <p className="mt-1 text-xs text-dune">{entityRelationCount[entity.name] || 0} relationships</p>
                        <p className="mt-2 text-[11px] text-dune">
                          {(entity.fields || []).slice(0, 3).map((field) => field.name).join("  •  ") || "id"}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              </section>

              <section className="glass rounded-3xl p-6 reveal">
                <div className="flex flex-wrap items-center gap-2">
                  {([
                    { key: "schema", label: "Schema" },
                    { key: "api", label: "API" },
                    { key: "code", label: "Code" },
                    { key: "sql", label: "SQL" },
                    { key: "rules", label: "Rules" }
                  ] as Array<{ key: OutputTab; label: string }>).filter((tab) => isTabAllowed(tab.key)).map((tab) => (
                    <button
                      key={tab.key}
                      type="button"
                      onClick={() => setActiveTab(tab.key)}
                      className={`rounded-full px-4 py-2 text-sm ${
                        activeTab === tab.key
                          ? "bg-ink text-bone"
                          : "border border-dune/30 bg-white text-ink"
                      }`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>

                <div className="mt-5 rounded-2xl border border-dune/20 bg-white/80 p-5">
                  <p className="mb-4 text-xs uppercase tracking-[0.16em] text-dune">
                    {isPlanLoading && !plan
                      ? "Loading plan outputs..."
                      : `${plan?.plan_name || "Current"} outputs: ${allowedTabs.map((tab) => tab.toUpperCase()).join(" • ")}`}
                  </p>
                  {isCompletedRun && (inferredBoostCount > 0 || expandedCharDelta > 0) ? (
                    <p className="mb-3 rounded-xl border border-emerald-300/70 bg-emerald-50 px-3 py-2 text-xs text-emerald-900">
                      Intelligence boost active: +{inferredBoostCount} inferred backend hints, +{expandedCharDelta} internal expansion chars.
                    </p>
                  ) : null}
                  {lockedTabs.length ? (
                    <p className="mb-3 rounded-xl border border-dune/25 bg-bone/60 px-3 py-2 text-xs text-dune">
                      Advanced output hidden on this plan: {lockedTabs.map((tab) => tab.toUpperCase()).join(" • ")}. Upgrade to unlock.
                    </p>
                  ) : null}
                  {showStarterLockedPreview ? (
                    <div className="mb-4 rounded-xl border border-dune/20 bg-white/70 p-3">
                      <p className="text-[11px] uppercase tracking-[0.14em] text-dune">Preview (Locked)</p>
                      <div className="mt-2 rounded-lg border border-dune/20 bg-bone/70 p-3 text-xs text-ink blur-[2px] select-none">
                        {starterLockedPreviewMessage}
                      </div>
                    </div>
                  ) : null}
                  {activeTab === "schema" ? (
                    <div className="grid gap-4 md:grid-cols-2">
                      {sortedEntities.map((entity, index) => (
                        <div key={`${entity.name}-${index}`} className={`min-w-0 rounded-2xl border ${highlightedEntities.has(entity.name) ? "border-ink/30" : "border-dune/20"} bg-white p-4`}>
                          <div className="flex items-center justify-between gap-2">
                            <p className="text-sm font-semibold text-ink">{entity.name}</p>
                            <span className="rounded-full border border-dune/25 bg-white px-2 py-0.5 text-[11px] text-dune">{entityRelationCount[entity.name] || 0} relations</span>
                          </div>
                          <div className="mt-3 space-y-1">
                            {(entity.fields?.length ? entity.fields : [{ name: "id", type: "uuid", constraints: ["primary_key"] }]).map((field, fieldIndex) => (
                              <div key={`${entity.name}-${field.name}-${fieldIndex}`} className="min-w-0 flex flex-wrap items-center gap-2 text-xs text-dune">
                                <span className="font-semibold text-ink">{field.name}</span>
                                <span className="rounded-full bg-ink px-2 py-0.5 text-[10px] uppercase tracking-[0.08em] text-bone">{field.type}</span>
                                {(field.constraints || []).slice(0, 2).map((constraint, constraintIndex) => renderConstraintChip(constraint, constraintIndex))}
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : null}

                  {activeTab === "api" ? (
                    <div className="space-y-3">
                      {endpoints.length ? endpoints.map((api, index) => (
                        <div key={`${api.method}-${api.path}-${index}`} className="rounded-2xl border border-dune/20 bg-white p-4">
                          <div className="flex items-center gap-3">
                            <span className="code-pill">{api.method}</span>
                            <span className="text-sm font-medium text-ink">{api.path}</span>
                          </div>
                          <p className="mt-2 text-xs text-dune">{api.desc || "Generated endpoint"}</p>
                          {!!api.errors?.length ? <p className="mt-1 text-[11px] text-dune/90">Errors: {api.errors.join(" | ")}</p> : null}
                        </div>
                      )) : <p className="text-sm text-dune">No API routes generated.</p>}
                    </div>
                  ) : null}

                  {activeTab === "code" && isTabAllowed("code") ? (
                    <div className="space-y-3">
                      <div className="rounded-2xl border border-dune/20 bg-white p-4">
                        <p className="text-xs uppercase tracking-[0.2em] text-dune">Models</p>
                        <pre className="mt-2 whitespace-pre-wrap text-xs text-ink">{codeSkeleton?.models || "No models generated yet."}</pre>
                      </div>
                      <div className="rounded-2xl border border-dune/20 bg-white p-4">
                        <p className="text-xs uppercase tracking-[0.2em] text-dune">Routers</p>
                        <pre className="mt-2 whitespace-pre-wrap text-xs text-ink">{codeSkeleton?.routers || "No routers generated yet."}</pre>
                      </div>
                      <div className="rounded-2xl border border-dune/20 bg-white p-4">
                        <p className="text-xs uppercase tracking-[0.2em] text-dune">Services</p>
                        <pre className="mt-2 whitespace-pre-wrap text-xs text-ink">{codeSkeleton?.services || "No services generated yet."}</pre>
                      </div>
                    </div>
                  ) : null}

                  {activeTab === "sql" && isTabAllowed("sql") ? (
                    <div>
                      <p className="text-xs text-dune">{migrationTableCount} tables detected in migration output.</p>
                      <pre className="mt-3 whitespace-pre-wrap rounded-2xl border border-dune/20 bg-white p-4 text-xs text-ink">{migrationSqlText || "No SQL migration generated yet."}</pre>
                    </div>
                  ) : null}

                  {activeTab === "rules" && isTabAllowed("rules") ? (
                    <div className="space-y-3">
                      {normalizedRules.length ? normalizedRules.map((rule, index) => (
                        <div key={`${rule.name}-${index}`} className="rounded-2xl border border-dune/20 bg-white p-4">
                          <p className="text-sm font-semibold text-ink">{rule.name}</p>
                          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-dune">
                            <span className="rounded-full border border-dune/20 bg-white px-2 py-0.5 uppercase tracking-[0.08em]">{rule.type}</span>
                            {rule.trigger_condition ? <span className="rounded-full border border-dune/20 bg-white px-2 py-0.5">Trigger: {rule.trigger_condition}</span> : null}
                          </div>
                        </div>
                      )) : <p className="text-sm text-dune">No business rules generated.</p>}
                    </div>
                  ) : null}
                </div>

                <div className="mt-5 flex flex-wrap gap-3">
                  {isTabAllowed("sql") ? (
                    <button className="rounded-full bg-ink px-5 py-2 text-sm text-bone" onClick={() => downloadTextFile("baxel-migration.sql", migrationSqlText || "-- No SQL generated yet.")}>Export SQL</button>
                  ) : (
                    <Link href="/pricing" className="rounded-full border border-dune/35 px-4 py-2 text-sm text-ink">Unlock SQL export</Link>
                  )}
                  <button className="rounded-full border border-dune/35 px-4 py-2 text-sm text-ink" onClick={copyShareLinkFromLatest}>Copy share link</button>
                  <button className="rounded-full border border-dune/35 px-4 py-2 text-sm text-ink disabled:cursor-not-allowed disabled:opacity-60" onClick={rerunLatest} disabled={isRerunBlocked}>Re-run</button>
                </div>
              </section>
            </div>
          ) : null}
        </main>

        <aside className="space-y-4">
          <section className="glass rounded-3xl p-8 reveal reveal-delay-1">
            <p className="label">What are you building?</p>
            <div className="mt-4 rounded-2xl border border-dune/20 bg-white/70 p-4">
              <p className="text-[11px] uppercase tracking-[0.2em] text-dune">Starter prompts</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {starterTemplates.map((template) => (
                  <button
                    key={template.label}
                    className="rounded-full border border-dune/30 px-3 py-1 text-xs text-ink"
                    onClick={() => {
                      setProjectName(template.projectName);
                      setIdeaName(template.projectName);
                      setSpecTitle(template.specTitle);
                      setSpecContent(template.specContent);
                    }}
                  >
                    {template.label}
                  </button>
                ))}
              </div>
              <div className="mt-4">
                <label className="text-xs uppercase tracking-[0.2em] text-dune">Idea name</label>
                <input
                  className="mt-2 w-full rounded-2xl border border-dune/20 bg-white/80 px-4 py-2 text-sm text-ink"
                  value={ideaName}
                  onChange={(event) => setIdeaName(event.target.value)}
                  placeholder="Example: LearnSphere"
                />
              </div>
            </div>

            {isRunning ? (
              <div className="mt-6 rounded-2xl border border-dune/25 bg-white/80 p-4">
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 animate-pulse rounded-full bg-ink" />
                  <p className="text-sm font-semibold text-ink">Generating backend...</p>
                </div>
                <p className="mt-2 text-xs text-dune">Current stage: {pipelineStages[processStageIndex] || "Preparing"}</p>
                <p className="mt-1 text-xs text-dune">{formatElapsed(elapsedSeconds)}</p>
                <button className="mt-4 min-h-[56px] w-full cursor-not-allowed rounded-2xl bg-ink/70 px-4 py-3 text-base font-semibold text-bone" disabled>
                  Running...
                </button>
              </div>
            ) : (
              <div className="mt-6 space-y-4 text-sm text-dune">
                <div>
                  <label className="text-xs uppercase tracking-[0.2em] text-dune">Describe your idea</label>
                  <textarea
                    className="mt-2 h-40 w-full rounded-2xl border border-dune/20 bg-white/70 px-4 py-3 text-sm"
                    value={specContent}
                    onChange={(event) => setSpecContent(event.target.value.slice(0, activeIdeaCharLimit))}
                    maxLength={activeIdeaCharLimit}
                    placeholder="A ride-sharing app where drivers accept trips, riders track ETAs, and payments settle after each ride..."
                  />
                  <p className="mt-2 text-xs text-dune">Hint: write this like you are explaining the product to a teammate.</p>
                  <p className="mt-1 text-xs text-dune">{ideaCharsUsed}/{activeIdeaCharLimit} characters used ({ideaCharsRemaining} left).</p>
                </div>
                <button
                  className={`min-h-[56px] w-full rounded-2xl px-4 py-3 text-base font-semibold ${isGenerateBlocked ? "cursor-not-allowed bg-ink/60 text-bone" : "bg-ink text-bone"}`}
                  onClick={runPipeline}
                  disabled={isGenerateBlocked}
                >
                  {isPlanLoading && !plan ? "Loading plan..." : isGenerateBlocked ? "Run limit reached" : "Generate backend"}
                </button>
                {isPlanLimitReached ? (
                  <p className="rounded-xl border border-amber-300/70 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                    You reached your {plan?.plan_name || "current"} plan limit. {planUsageText}. You can still re-run existing specs while run credits remain. <Link href="/pricing" className="underline">View pricing</Link>
                  </p>
                ) : null}
                {plan ? (
                  <p className="text-xs text-dune">
                    Plan budget guide: {plan.monthly_run_limit} runs across {plan.monthly_project_limit} projects (about {perProjectRunsAllowed} runs/project). Idea limit: {activeIdeaCharLimit} chars.
                  </p>
                ) : null}
              </div>
            )}

            {isIdle ? (
              <div className="mt-5 rounded-2xl border border-dune/20 bg-white/70 p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-dune">Last run</p>
                <p className="mt-2 text-sm font-semibold text-ink">{summary?.recent_pipeline_runs?.[0]?.spec_title || "No runs yet"}</p>
                <p className="text-xs text-dune">{summary?.recent_pipeline_runs?.[0]?.project_name || ""}</p>
                <button className="mt-3 rounded-full border border-dune/35 px-3 py-1.5 text-xs text-ink disabled:cursor-not-allowed disabled:opacity-60" onClick={rerunLatest} disabled={isRerunBlocked}>Re-run</button>
              </div>
            ) : null}

            {isCompletedRun ? (
              <div className="mt-5 rounded-2xl border border-dune/20 bg-white/80 p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-dune">Run complete</p>
                <p className="mt-2 text-sm font-semibold text-ink">{lastRunMeta?.projectName || projectName || "Project"}</p>
                <p className="text-xs text-dune">{lastRunMeta?.specTitle || specTitle || "Spec"}</p>
                <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
                  <div className="rounded-xl border border-dune/20 bg-white px-2 py-2"><p className="font-semibold text-ink">{entities.length}</p><p className="text-dune">Entities</p></div>
                  <div className="rounded-xl border border-dune/20 bg-white px-2 py-2"><p className="font-semibold text-ink">{endpoints.length}</p><p className="text-dune">Endpoints</p></div>
                  <div className="rounded-xl border border-dune/20 bg-white px-2 py-2"><p className="font-semibold text-ink">{migrationTableCount}</p><p className="text-dune">SQL tables</p></div>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button className="rounded-full border border-dune/35 px-3 py-1.5 text-xs text-ink" onClick={() => downloadTextFile("baxel-migration.sql", migrationSqlText || "-- No SQL generated yet.")}>Export SQL</button>
                  <button className="rounded-full border border-dune/35 px-3 py-1.5 text-xs text-ink" onClick={copyShareLinkFromLatest}>Copy share link</button>
                  <button className="rounded-full border border-dune/35 px-3 py-1.5 text-xs text-ink disabled:cursor-not-allowed disabled:opacity-60" onClick={rerunLatest} disabled={isRerunBlocked}>Re-run</button>
                </div>
              </div>
            ) : null}
          </section>

          <section className="glass rounded-2xl p-4">
            <p className="label">Stats</p>
            <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs text-dune">
              <div className="rounded-xl border border-dune/20 bg-white/70 px-2 py-2"><p className="text-base font-semibold text-ink">{summary?.projects_count ?? 0}</p><p>Projects</p></div>
              <div className="rounded-xl border border-dune/20 bg-white/70 px-2 py-2"><p className="text-base font-semibold text-ink">{summary?.specs_count ?? 0}</p><p>Specs</p></div>
              <div className="rounded-xl border border-dune/20 bg-white/70 px-2 py-2"><p className="text-base font-semibold text-ink">{summary?.pipeline_runs_count ?? 0}</p><p>Runs</p></div>
            </div>
          </section>

          <section className="glass rounded-2xl p-4">
            <p className="label">Active projects</p>
            <div className="mt-3 space-y-2">
              {(summary?.recent_projects?.length
                ? summary.recent_projects
                : [{ id: "draft-project", name: projectName || "No recent project", created_at: "" }])
                .slice(0, 6)
                .map((project, index) => (
                  <div key={`${project.id}-${project.name}-${index}`} className="rounded-xl border border-dune/20 bg-white/70 px-3 py-2">
                    <p className="truncate text-xs font-medium text-ink">{project.name}</p>
                    <p className="text-[11px] text-dune">{project.created_at ? new Date(project.created_at).toLocaleDateString() : "-"}</p>
                  </div>
                ))}
            </div>
          </section>

          <section className="glass rounded-2xl p-4">
            <p className="text-[10px] uppercase tracking-[0.22em] text-dune/80">Output detail</p>
            <div className="mt-3 flex items-center gap-2">
              {([
                { label: "Guide", value: "guide" as ViewMode },
                { label: "Builder", value: "builder" as ViewMode },
                { label: "Pro", value: "pro" as ViewMode }
              ]).map((item) => (
                <button
                  key={item.value}
                  type="button"
                  onClick={() => setAndPersistViewMode(item.value)}
                  className={`rounded-full px-3 py-1.5 text-xs ${
                    viewMode === item.value
                      ? "bg-ink text-bone ring-2 ring-ink/25"
                      : "border border-dune/35 bg-white text-dune"
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </section>
        </aside>
      </div>
    </AppShell>
  );
}
