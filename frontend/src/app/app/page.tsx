import Link from "next/link";
import AppShell from "../components/app-shell";

export default function AppIndexPage() {
  return (
    <AppShell>
      <div className="glass rounded-3xl p-8">
        <p className="label">Workspace</p>
        <h1 className="mt-4 text-2xl font-semibold text-ink">Choose a project to continue.</h1>
        <p className="mt-2 text-sm text-dune">Jump into your dashboard to keep shaping the backend.</p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link href="/app/dashboard" className="rounded-full bg-ink px-4 py-2 text-sm text-bone">
            Open dashboard
          </Link>
          <Link href="/" className="rounded-full border border-dune/40 px-4 py-2 text-sm">
            Back to marketing
          </Link>
        </div>
      </div>
    </AppShell>
  );
}
