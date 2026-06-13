"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import AppShell from "../../components/app-shell";
import { supabase } from "../../../lib/supabase-browser";

type PipelineResult = {
  summary?: { summary?: string } | string;
  overview?: {
    product?: string;
    summary?: string;
    assumptions?: string[];
    primary_users?: string[];
  };
  requirements?: {
    functional?: string[];
    non_functional?: string[];
    constraints?: string[];
    integrations?: string[];
    data_sensitivity?: string;
    compliance?: string[];
  };
  architecture?: {
    style?: string;
    services?: string[];
    data_stores?: string[];
    messaging?: string[];
    cache?: string[];
    external?: string[];
    deployment?: string[];
  };
  data_model?: {
    entities?: Array<{
      name: string;
      fields?: Array<{
        name: string;
        type: string;
        constraints?: string[];
        description?: string;
      }>;
    }>;
    relationships?: string[];
    indexes?: string[];
    retention?: string[];
  };
  api?: {
    public_endpoints?: Array<{ method: string; path: string; desc?: string }>;
    internal_endpoints?: Array<{ method: string; path: string; desc?: string }>;
    webhooks?: Array<{ event: string; path: string; desc?: string }>;
  };
  workflows?: Array<{ name: string; steps?: string[]; failure_modes?: string[] }>;
  security?: {
    authn?: string;
    authz?: string;
    data_protection?: string;
    audit?: string;
  };
  observability?: {
    logs?: string[];
    metrics?: string[];
    traces?: string[];
    alerts?: string[];
  };
  scaling?: {
    current?: string[];
    future?: string[];
    bottlenecks?: string[];
  };
  reliability?: {
    slo?: string[];
    backups?: string[];
    dr?: string[];
  };
  deliverables?: {
    milestones?: string[];
    testing?: string[];
    runbooks?: string[];
  };
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
  anti_fragility?: {
    resilience_rating: string;
    critical_vulnerabilities: string[];
    chaos_scenarios: Array<{
      scenario_name: string;
      failure_description: string;
      impact_analysis: string;
      mitigation_strategy: string;
    }>;
    hardening_checklist: string[];
  };
};

type OutputTab = "schema" | "api" | "code" | "sql" | "rules" | "resilience";

type Message = {
  role: "user" | "assistant";
  content: string;
};

// Markdown Renderer Component
function MarkdownRenderer({ content }: { content: string }) {
  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];
  let currentListItems: React.ReactNode[] = [];
  let activeListType: "unordered" | "ordered" | null = null;

  const flushList = (key: string | number) => {
    if (currentListItems.length > 0) {
      if (activeListType === "unordered") {
        elements.push(
          <ul key={`list-${key}`} className="list-disc pl-5 mb-3 last:mb-0 space-y-1">
            {currentListItems}
          </ul>
        );
      } else if (activeListType === "ordered") {
        elements.push(
          <ol key={`list-${key}`} className="list-decimal pl-5 mb-3 last:mb-0 space-y-1">
            {currentListItems}
          </ol>
        );
      }
      currentListItems = [];
      activeListType = null;
    }
  };

  const parseInlineStyles = (text: string) => {
    // Split by bold markdown **
    const parts = text.split(/\*\*([^*]+)\*\*/g);
    return parts.map((part, index) => {
      if (index % 2 === 1) {
        return <strong key={index} className="font-bold text-[#C2D68C]">{part}</strong>;
      }
      // Inline code `code`
      const subParts = part.split(/`([^`]+)`/g);
      return subParts.map((subPart, subIndex) => {
        if (subIndex % 2 === 1) {
          return (
            <code key={`code-${index}-${subIndex}`} className="bg-white/10 px-1.5 py-0.5 rounded font-mono text-xs text-[#C2D68C]">
              {subPart}
            </code>
          );
        }
        return subPart;
      });
    });
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    // Check matches
    const isBulletMatch = trimmed.startsWith("* ") || trimmed.startsWith("- ") || trimmed.startsWith("• ");
    const isOrderedMatch = /^\d+\.\s+/.test(trimmed);

    if (isBulletMatch) {
      if (activeListType !== "unordered") {
        flushList(i);
        activeListType = "unordered";
      }
      const cleanText = trimmed.replace(/^[\*\-•]\s+/, "");
      currentListItems.push(
        <li key={`li-${i}`} className="text-white/90">
          {parseInlineStyles(cleanText)}
        </li>
      );
    } else if (isOrderedMatch) {
      if (activeListType !== "ordered") {
        flushList(i);
        activeListType = "ordered";
      }
      const cleanText = trimmed.replace(/^\d+\.\s+/, "");
      currentListItems.push(
        <li key={`li-${i}`} className="text-white/90">
          {parseInlineStyles(cleanText)}
        </li>
      );
    } else {
      flushList(i);

      if (trimmed === "") {
        continue;
      }

      if (trimmed.startsWith("### ")) {
        elements.push(
          <h4 key={`h3-${i}`} className="text-xs font-bold text-[#C2D68C] mt-3 mb-1 uppercase tracking-wider">
            {parseInlineStyles(trimmed.substring(4))}
          </h4>
        );
      } else if (trimmed.startsWith("## ")) {
        elements.push(
          <h3 key={`h2-${i}`} className="text-sm font-bold text-white mt-4 mb-1.5">
            {parseInlineStyles(trimmed.substring(3))}
          </h3>
        );
      } else if (trimmed.startsWith("# ")) {
        elements.push(
          <h2 key={`h1-${i}`} className="text-base font-bold text-white mt-5 mb-2">
            {parseInlineStyles(trimmed.substring(2))}
          </h2>
        );
      } else {
        elements.push(
          <p key={`p-${i}`} className="mb-2 last:mb-0 text-white/90 leading-relaxed">
            {parseInlineStyles(trimmed)}
          </p>
        );
      }
    }
  }

  flushList("final");

  return <div className="space-y-1">{elements}</div>;
}

const starterPrompts = [
  { label: "Investor Summary", text: "Write a short summary of this architecture that I can pitch to investors." },
  { label: "AWS Cost Estimate", text: "Estimate how much this stack will cost to host on AWS for 10,000 users/month." },
  { label: "Prisma Schema", text: "Can you generate a Prisma schema file matching the database design?" },
  { label: "Security Review", text: "What security considerations or vulnerabilities are most critical for these API routes?" }
];

function ChatbotContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const apiBaseUrl = useMemo(
    () => process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000",
    []
  );

  const runId = searchParams.get("run");
  const specId = searchParams.get("spec_id");
  const fallbackTitle = searchParams.get("title") || "Generated Spec";
  const fallbackProject = searchParams.get("project") || "Default Project";

  const [result, setResult] = useState<PipelineResult | null>(null);
  const [activeTab, setActiveTab] = useState<OutputTab>("schema");
  const [status, setStatus] = useState("Loading spec details...");
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "Welcome to SAGE! I am SAGE (Specification Answering & Guidance Engine), your AI Systems Architect. Ask me anything about the generated design, databases, API logic, scaling properties, or request code helpers (like ORM files/models)."
    }
  ]);
  const [chatInput, setChatInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [errorText, setErrorText] = useState("");
  
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  const getAccessToken = async () => {
    const { data } = await supabase.auth.getSession();
    return data.session?.access_token || null;
  };

  const getAuthHeaders = (token: string) => ({
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`
  });

  const scrollChatToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollChatToBottom();
  }, [messages, isTyping]);

  useEffect(() => {
    if (!runId) {
      setStatus("No run context selected. Please select a project run from the dashboard.");
      return;
    }

    const loadSpecContext = async () => {
      try {
        const token = await getAccessToken();
        if (!token) {
          setStatus("Sign in to load specification.");
          return;
        }

        const runRes = await fetch(`${apiBaseUrl}/pipelines/${runId}`, {
          headers: getAuthHeaders(token)
        });
        if (!runRes.ok) {
          setStatus("Failed to fetch generating context.");
          return;
        }

        const payload = await runRes.json();
        if (payload.result) {
          setResult(payload.result);
          setStatus("Ready");
          
          if (specId) {
            try {
              const historyRes = await fetch(`${apiBaseUrl}/api/chat/history?spec_id=${specId}`, {
                headers: getAuthHeaders(token)
              });
              if (historyRes.ok) {
                const historyData = await historyRes.json();
                if (historyData.messages && historyData.messages.length > 0) {
                  setMessages([
                    {
                      role: "assistant",
                      content: "Welcome to SAGE! I am SAGE (Specification Answering & Guidance Engine), your AI Systems Architect. Ask me anything about the generated design, databases, API logic, scaling properties, or request code helpers (like ORM files/models)."
                    },
                    ...historyData.messages
                  ]);
                }
              }
            } catch (err) {
              console.error("Failed to load chat history:", err);
            }
          }
        } else {
          setStatus("No results generated for this run.");
        }
      } catch {
        setStatus("Network error loading run context.");
      }
    };

    loadSpecContext();
  }, [runId, apiBaseUrl]);

  // Spec helper parsing
  const entities = result?.entities || [];
  const endpoints = result?.endpoints || [];
  const rules = result?.rules || [];
  const relationships = result?.relationships || [];
  const codeSkeleton = result?.code_skeleton;

  const normalizeSqlText = (value: unknown): string => {
    if (Array.isArray(value)) {
      return value.map((item) => normalizeSqlText(item)).filter(Boolean).join("\n\n");
    }
    const text = String(value || "").trim();
    if (!text) return "";
    return text.replace(/\\n/g, "\n");
  };

  const migrationSqlText = normalizeSqlText(result?.migration_sql);
  const migrationTableCount = (migrationSqlText.match(/create\s+table/gi) || []).length;

  const normalizedRules = (rules.length ? rules : [
    "Every entity needs a primary key",
    "Many-to-many requires a join table",
    "Every endpoint includes error shapes"
  ]).map((rule) => {
    if (typeof rule === "string") return { name: rule, type: "rule", trigger_condition: "" };
    return { name: rule.name || "Rule", type: rule.type || "rule", trigger_condition: rule.trigger_condition || "" };
  });

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
        className="rounded-full border border-white/20 bg-white/5 px-2 py-0.5 text-[9px] uppercase tracking-[0.08em] text-white/60"
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

  const handleSendMessage = async (textToSend: string) => {
    const trimmed = textToSend.trim();
    if (!trimmed || isTyping) return;

    if (!specId) {
      setErrorText("Error: No spec_id available for chatbot query context.");
      return;
    }

    setErrorText("");
    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setChatInput("");
    setIsTyping(true);

    try {
      const token = await getAccessToken();
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const res = await fetch(`${apiBaseUrl}/api/chat`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          message: trimmed,
          spec_id: specId
        })
      });

      if (!res.ok) {
        throw new Error(await res.text() || "Chat failure");
      }

      const payload = await res.json();
      setMessages((prev) => [...prev, { role: "assistant", content: payload.reply || "No response content." }]);
    } catch (err) {
      setErrorText(`Failed to generate AI response. Details: ${String((err as Error)?.message || err)}`);
    } finally {
      setIsTyping(false);
    }
  };

  if (status !== "Ready") {
    return (
      <AppShell>
        <div className="glass rounded-3xl p-8 text-center text-white/60">
          <p className="label">SAGE Chat</p>
          <p className="mt-4 text-sm">{status}</p>
          <div className="mt-6">
            <Link href="/app/dashboard" className="rounded-full bg-[#C2D68C] px-5 py-2 text-xs font-semibold text-[#1F261D]">
              Back to dashboard
            </Link>
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell wide>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-xs text-white/50">
            <Link href="/app/dashboard" className="transition hover:text-white">Dashboard</Link>
            <span>/</span>
            <span className="text-white/80">SAGE Chat</span>
          </div>
          <h1 className="mt-2 text-2xl font-bold text-white">
            Chatting with {fallbackProject || result?.overview?.product || "Spec Context"}
          </h1>
          <p className="text-sm text-white/60">{fallbackTitle}</p>
        </div>
        <Link href="/app/dashboard" className="rounded-full border border-white/20 bg-white/5 px-4 py-2 text-xs font-medium text-white transition hover:bg-white/10">
          ← Back to Workspace
        </Link>
      </div>

      <div className="grid gap-6 lg:grid-cols-[0.85fr_1.15fr] h-[calc(100vh-220px)] min-h-[550px]">
        {/* Left Visual Spec Column */}
        <section className="glass rounded-3xl p-6 flex flex-col min-h-0">
          <div className="flex flex-wrap items-center gap-1.5 pb-4 border-b border-white/10">
            {([
              { key: "schema", label: "Schema" },
              { key: "api", label: "API" },
              { key: "code", label: "Code" },
              { key: "sql", label: "SQL" },
              { key: "rules", label: "Rules" },
              { key: "resilience", label: "Resilience" }
            ] as Array<{ key: OutputTab; label: string }>).map((tab) => (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveTab(tab.key)}
                className={`rounded-full px-3 py-1.5 text-xs font-medium transition-all ${
                  activeTab === tab.key
                    ? "bg-[#C2D68C] text-[#1F261D]"
                    : "border border-white/20 bg-white/5 text-white/70 hover:text-white"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="mt-4 flex-1 overflow-y-auto pr-1">
            {activeTab === "schema" && (
              <div className="grid gap-4 md:grid-cols-2">
                {entities.map((entity, index) => (
                  <div key={`${entity.name}-${index}`} className="rounded-2xl border border-white/20 bg-white/5 p-4">
                    <p className="text-sm font-semibold text-white">{entity.name}</p>
                    <div className="mt-3 space-y-1.5">
                      {(entity.fields || []).map((field, fieldIndex) => (
                        <div key={`${entity.name}-${field.name}-${fieldIndex}`} className="flex flex-wrap items-center gap-2 text-xs text-white/60">
                          <span className="font-semibold text-white">{field.name}</span>
                          <span className="rounded-full bg-white/10 px-1.5 py-0.5 text-[9px] uppercase tracking-[0.08em] text-white">{field.type}</span>
                          {(field.constraints || []).map((constraint, cIdx) => renderConstraintChip(constraint, cIdx))}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {activeTab === "api" && (
              <div className="space-y-3">
                {endpoints.length ? endpoints.map((api, index) => (
                  <div key={`${api.method}-${api.path}-${index}`} className="rounded-2xl border border-white/20 bg-white/5 p-4">
                    <div className="flex items-center gap-2">
                      <span className="code-pill uppercase font-semibold text-[10px]">{api.method}</span>
                      <span className="text-xs font-medium text-white">{api.path}</span>
                    </div>
                    <p className="mt-2 text-xs text-white/60">{api.desc || "Generated endpoint"}</p>
                    {!!api.errors?.length && (
                      <p className="mt-1 text-[10px] text-white/50">Possible Errors: {api.errors.join(" | ")}</p>
                    )}
                  </div>
                )) : <p className="text-sm text-white/60">No API routes available.</p>}
              </div>
            )}

            {activeTab === "code" && (
              <div className="space-y-3">
                <div className="rounded-2xl border border-white/20 bg-white/5 p-4">
                  <p className="text-xs uppercase tracking-[0.2em] text-[#C2D68C]">Models</p>
                  <pre className="mt-2 whitespace-pre-wrap font-mono text-[11px] text-white">{codeSkeleton?.models || "No models skeleton generated."}</pre>
                </div>
                <div className="rounded-2xl border border-white/20 bg-white/5 p-4">
                  <p className="text-xs uppercase tracking-[0.2em] text-[#C2D68C]">Routers</p>
                  <pre className="mt-2 whitespace-pre-wrap font-mono text-[11px] text-white">{codeSkeleton?.routers || "No routers skeleton generated."}</pre>
                </div>
              </div>
            )}

            {activeTab === "sql" && (
              <div>
                <p className="text-xs text-white/60">{migrationTableCount} tables detected in migration.</p>
                <pre className="mt-3 whitespace-pre-wrap font-mono text-[11px] rounded-2xl border border-white/20 bg-white/5 p-4 text-white">{migrationSqlText || "No SQL migration."}</pre>
              </div>
            )}

            {activeTab === "rules" && (
              <div className="space-y-3">
                {normalizedRules.map((rule, index) => (
                  <div key={`${rule.name}-${index}`} className="rounded-2xl border border-white/20 bg-white/5 p-4">
                    <p className="text-sm font-semibold text-white">{rule.name}</p>
                    <div className="mt-2 flex items-center gap-2 text-[10px] text-white/60">
                      <span className="rounded-full border border-white/25 bg-white/5 px-2 py-0.5 uppercase">{rule.type}</span>
                      {rule.trigger_condition && <span>Trigger: {rule.trigger_condition}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {activeTab === "resilience" && (
              <div className="space-y-4">
                <div className="flex items-center justify-between gap-4 rounded-xl border border-white/10 bg-white/5 p-4">
                  <div>
                    <h3 className="text-sm font-bold text-white">Resilience Hardening Audit</h3>
                    <p className="text-xs text-white/60">Automated chaos engineering analysis</p>
                  </div>
                  <span className="rounded-lg bg-emerald-500/20 border border-emerald-500/30 px-3 py-1 font-mono text-xl font-bold text-emerald-400">
                    {result?.anti_fragility?.resilience_rating || "B+"}
                  </span>
                </div>

                <div className="rounded-xl border border-rose-500/20 bg-rose-500/5 p-4">
                  <h4 className="text-xs font-semibold uppercase tracking-[0.1em] text-rose-300">Vulnerabilities</h4>
                  <ul className="mt-2 space-y-1.5">
                    {(result?.anti_fragility?.critical_vulnerabilities || [
                      "Potential thread exhaust under heavy async pipeline requests.",
                      "Single point of database instance failure."
                    ]).map((vuln, i) => (
                      <li key={i} className="text-xs text-white/80 list-disc list-inside">{vuln}</li>
                    ))}
                  </ul>
                </div>

                <div className="grid gap-3 md:grid-cols-2">
                  {(result?.anti_fragility?.chaos_scenarios || []).map((scenario, idx) => (
                    <div key={idx} className="rounded-xl border border-white/15 bg-white/5 p-4">
                      <span className="rounded-full bg-white/10 px-2 py-0.5 text-[9px] font-semibold text-[#C2D68C] uppercase">Scenario {idx+1}</span>
                      <h5 className="mt-2 text-xs font-bold text-white">{scenario.scenario_name}</h5>
                      <p className="mt-1 text-[11px] text-white/60"><strong className="text-rose-300">Failure:</strong> {scenario.failure_description}</p>
                      <p className="mt-1 text-[11px] text-[#C2D68C]"><strong className="text-emerald-300">Mitigate:</strong> {scenario.mitigation_strategy}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Right Chat Column */}
        <section className="glass rounded-3xl p-6 flex flex-col min-h-0 border border-[#C2D68C]/20 shadow-[0_8px_32px_rgba(194,214,140,0.05)]">
          <p className="label border-b border-white/10 pb-3">SAGE Chat</p>

          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto mt-4 space-y-4 pr-1">
            {messages.map((msg, index) => (
              <div key={index} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[85%] rounded-2xl p-4 text-sm leading-relaxed ${
                    msg.role === "user"
                      ? "bg-[#C2D68C]/15 text-white border border-[#C2D68C]/35 rounded-tr-none"
                      : "bg-white/5 text-white/90 border border-white/10 rounded-tl-none"
                  }`}
                >
                  <MarkdownRenderer content={msg.content} />
                </div>
              </div>
            ))}
            {isTyping && (
              <div className="flex justify-start">
                <div className="rounded-2xl bg-white/5 border border-white/10 p-3 rounded-tl-none flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 animate-bounce bg-[#C2D68C] rounded-full" />
                  <span className="h-1.5 w-1.5 animate-bounce bg-[#C2D68C] rounded-full [animation-delay:0.2s]" />
                  <span className="h-1.5 w-1.5 animate-bounce bg-[#C2D68C] rounded-full [animation-delay:0.4s]" />
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Starter prompts if only welcome msg is present */}
          {messages.length === 1 && (
            <div className="mt-4 pt-3 border-t border-white/5">
              <p className="text-[10px] uppercase tracking-wider text-white/40 mb-2">Starter prompts</p>
              <div className="grid grid-cols-2 gap-2">
                {starterPrompts.map((p) => (
                  <button
                    key={p.label}
                    onClick={() => handleSendMessage(p.text)}
                    className="text-left rounded-xl border border-white/10 bg-white/5 p-2 text-[10px] text-white/70 hover:border-[#C2D68C]/40 hover:text-white transition-all"
                  >
                    <div className="font-semibold text-[#C2D68C] mb-0.5">{p.label}</div>
                    <div className="line-clamp-2 text-white/50">{p.text}</div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {errorText && (
            <p className="mt-3 text-xs text-red-400 bg-red-950/20 border border-red-500/20 rounded-xl px-3 py-2">
              {errorText}
            </p>
          )}

          {/* Input Area */}
          <div className="mt-4 pt-4 border-t border-white/10">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage(chatInput);
              }}
              className="flex gap-2"
            >
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Ask a question about database connections, AWS hosting cost, GDPR..."
                className="flex-1 rounded-xl border border-white/20 bg-white/5 px-4 py-2.5 text-xs text-white placeholder-white/30 focus:border-[#C2D68C] focus:outline-none focus:ring-0"
                disabled={isTyping}
              />
              <button
                type="submit"
                className="rounded-xl bg-[#C2D68C] px-4 py-2 text-xs font-semibold text-[#1F261D] transition-all hover:bg-[#b0c878] disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={!chatInput.trim() || isTyping}
              >
                Send
              </button>
            </form>
          </div>
        </section>
      </div>
    </AppShell>
  );
}

export default function ChatbotPage() {
  return (
    <Suspense fallback={<AppShell><div className="p-10 text-white/60 text-center">Loading SAGE...</div></AppShell>}>
      <ChatbotContent />
    </Suspense>
  );
}
