"use client";

import React from "react";

export default function AnimatedBackground() {
  return (
    <div className="fixed inset-0 z-0 overflow-hidden pointer-events-none">
      {/* Orb 1: Soft Pistachio */}
      <div 
        className="absolute w-[800px] h-[800px] opacity-60 animate-blob"
        style={{
          background: 'radial-gradient(circle, #C2D68C 0%, rgba(194,214,140,0) 70%)',
          top: '-10%',
          left: '-10%',
          animationDelay: '0s'
        }}
      />
      
      {/* Orb 2: Moss Green */}
      <div 
        className="absolute w-[1000px] h-[1000px] opacity-40 animate-blob"
        style={{
          background: 'radial-gradient(circle, #869E58 0%, rgba(134,158,88,0) 70%)',
          top: '20%',
          right: '-20%',
          animationDelay: '3s',
          animationDuration: '20s'
        }}
      />

      {/* Orb 3: Very Soft Greenish Beige */}
      <div 
        className="absolute w-[800px] h-[800px] opacity-50 animate-blob"
        style={{
          background: 'radial-gradient(circle, #E5EBCC 0%, rgba(229,235,204,0) 70%)',
          bottom: '-20%',
          left: '30%',
          animationDelay: '5s',
          animationDuration: '18s'
        }}
      />
    </div>
  );
}
