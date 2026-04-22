"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import AnimatedBackground from "./animated-background";
import { motion, useScroll, useTransform } from "framer-motion";

const navLinks = [
  { label: "Overview", href: "/" },
  { label: "Technology", href: "/features" },
  { label: "Pipeline", href: "/pipeline" },
  { label: "Specs", href: "/docs" },
  { label: "Pricing", href: "/pricing" }
];

export default function MarketingShell({ children }: { children: React.ReactNode }) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const [isScrolled, setIsScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 50);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <div ref={rootRef} className="min-h-screen text-[#0b0d12] selection:bg-[#C2D68C]/30 relative">
      <AnimatedBackground />
      <header
        className={`fixed top-4 left-1/2 -translate-x-1/2 z-50 w-[95%] max-w-4xl rounded-full backdrop-blur-2xl border transition-all duration-500 ${
          isScrolled 
            ? "bg-[#1F261D]/70 border-white/20 py-2.5 shadow-2xl" 
            : "bg-[#1F261D]/60 border-white/10 py-2.5 shadow-lg"
        }`}
      >
        <div className="mx-auto flex items-center justify-between px-6">
          <Link href="/" className="flex items-center gap-3 group">
            <Image src="/logo.png" alt="Baxel Logo" width={24} height={24} className="rounded-md object-cover" />
            <p className="text-sm font-semibold tracking-tight text-white/90 group-hover:text-white transition-colors">
              Baxel
            </p>
          </Link>
          
          <nav className="hidden items-center gap-8 lg:flex">
            {navLinks.map((link) => (
              <Link 
                key={link.href} 
                href={link.href} 
                className="text-[13px] font-medium text-white/60 hover:text-white transition-colors"
              >
                {link.label}
              </Link>
            ))}
          </nav>
          
          <div className="flex items-center gap-4">
            <Link
              href="/auth"
              className="text-[13px] font-medium text-white/70 hover:text-white transition-colors"
            >
              Sign in
            </Link>
            <Link 
              href="/auth" 
              className="rounded-full bg-[#C2D68C] px-5 py-2 text-[13px] font-medium text-[#1F261D] shadow-[0_0_15px_rgba(194,214,140,0.3)] transition-transform hover:scale-105"
            >
              Experience Baxel
            </Link>
          </div>
        </div>
      </header>
      
      {/* Remove top padding because we want the Canvas to be edge-to-edge */}
      <div className="flex flex-col relative z-10">
        {children}
      </div>

      <footer className="w-full bg-[#1F261D] text-white border-t border-black/10 mt-16 relative z-10 rounded-t-[3rem] px-8 py-16">
        <div className="mx-auto max-w-6xl flex flex-col md:flex-row justify-between gap-12">
          <div className="max-w-sm">
            <div className="flex items-center gap-3 mb-4">
              <Image src="/logo.png" alt="Baxel Logo" width={28} height={28} className="rounded-md object-cover" />
              <p className="text-lg font-semibold tracking-tight">Baxel</p>
            </div>
            <p className="text-sm text-white/60 leading-relaxed">
              Turn messy product specs into production-ready backend architecture in minutes. Stop writing boilerplate, start building features.
            </p>
            <p className="mt-8 text-xs text-white/40">© {new Date().getFullYear()} Baxel Inc. All rights reserved.</p>
          </div>
          
          <div className="flex gap-16">
            <div className="flex flex-col gap-4">
              <p className="text-xs uppercase tracking-[0.2em] text-[#C2D68C]">Product</p>
              <Link href="/pricing" className="text-sm text-white/60 hover:text-white transition-colors">Pricing</Link>
              <Link href="/auth" className="text-sm text-white/60 hover:text-white transition-colors">Sign In</Link>
              <Link href="/auth" className="text-sm text-white/60 hover:text-white transition-colors">Start Free</Link>
            </div>
            <div className="flex flex-col gap-4">
              <p className="text-xs uppercase tracking-[0.2em] text-[#C2D68C]">Resources</p>
              <Link href="/docs" className="text-sm text-white/60 hover:text-white transition-colors">Documentation</Link>
              <Link href="/blog" className="text-sm text-white/60 hover:text-white transition-colors">Blog</Link>
              <Link href="/status" className="text-sm text-white/60 hover:text-white transition-colors">System Status</Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

