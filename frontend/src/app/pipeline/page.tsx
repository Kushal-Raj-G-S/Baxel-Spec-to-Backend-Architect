import MarketingShell from "../components/marketing-shell";

const pipelineSteps = [
  {
    step: "01",
    title: "Ingest PRD & Normalize Language",
    desc: "Baxel reads your messy product requirements, user stories, or unstructured ideas and uses multi-agent reasoning to normalize the terminology across the entire spec.",
  },
  {
    step: "02",
    title: "Extract Entities & Relationships",
    desc: "Automatically identifies core data models, their attributes, and how they relate to one another, forming an initial Entity-Relationship blueprint.",
  },
  {
    step: "03",
    title: "Draft API Surface",
    desc: "Generates REST and OpenAPI definitions for required endpoints, complete with request payloads, response shapes, and error contracts.",
  },
  {
    step: "04",
    title: "Surface Gaps & Business Rules",
    desc: "Analyzes invariants and compliance checks, highlighting conflicts or missing logic as actionable checklists for you to resolve before generating code.",
  },
  {
    step: "05",
    title: "Generate Code Skeleton",
    desc: "Transforms the finalized architecture into production-ready FastAPI or Node.js boilerplates with migrations, routing, and database integrations.",
  },
  {
    step: "06",
    title: "Push & Deploy",
    desc: "Commits the generated skeleton directly to your GitHub repository or provides a downloadable ZIP, ready for your team to start building features.",
  }
];

export default function PipelinePage() {
  return (
    <MarketingShell>
      <main className="mx-auto w-full max-w-6xl px-6 pb-16 pt-32 relative z-10">
        <section className="rounded-[2.5rem] bg-[#1F261D] border border-black/5 shadow-2xl p-10 md:p-14 reveal magnetic">
          <p className="text-xs uppercase tracking-[0.2em] text-[#C2D68C]">Pipeline</p>
          <h1 className="mt-4 text-3xl font-semibold text-white md:text-5xl">
            The intelligent extraction process.
          </h1>
          <p className="mt-4 max-w-2xl text-sm md:text-base text-white/60 leading-relaxed">
            From raw text to a deployable backend. See exactly how Baxel interprets your product intent at every step of the journey.
          </p>
          
          <div className="mt-16 space-y-8 relative before:absolute before:inset-0 before:left-5 md:before:left-1/2 md:before:-ml-[1px] before:h-full before:w-0.5 before:bg-gradient-to-b before:from-transparent before:via-white/10 before:to-transparent">
            {pipelineSteps.map((item, index) => (
              <div key={item.step} className={`relative flex items-center md:justify-between group is-active ${index % 2 === 0 ? 'md:flex-row-reverse' : 'md:flex-row'}`}>
                
                {/* The empty spacer for alternate alignment on desktop */}
                <div className="hidden md:block w-[calc(50%-2.5rem)]" />
                
                {/* The marker */}
                <div className="absolute left-0 top-1/2 -translate-y-1/2 md:static md:transform-none flex items-center justify-center w-10 h-10 rounded-full border-4 border-[#1F261D] bg-[#869E58] text-[#1F261D] font-bold text-xs shrink-0 shadow-[0_0_15px_rgba(134,158,88,0.4)] z-10 transition-transform group-hover:scale-110 md:mx-auto">
                  {item.step}
                </div>
                
                {/* The content box */}
                <div className={`w-[calc(100%-4rem)] ml-16 md:ml-0 md:w-[calc(50%-2.5rem)] p-6 rounded-2xl border border-white/5 bg-white/5 transition-all hover:bg-white/10 hover:border-white/10 shadow-lg reveal magnetic ${index % 2 === 0 ? 'md:text-right' : 'md:text-left'}`}>
                  <h3 className="text-lg font-semibold text-white">{item.title}</h3>
                  <p className="mt-2 text-sm text-white/60 leading-relaxed">{item.desc}</p>
                </div>
                
              </div>
            ))}
          </div>
        </section>
      </main>
    </MarketingShell>
  );
}
