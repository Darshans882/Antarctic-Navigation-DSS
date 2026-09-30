import type { ReactNode } from "react";
import bgImage from "../../../background image.png";

interface AntarcticPageHeaderProps {
  title: string;
  titleHighlight: string;
  subtitle: ReactNode;
  rightControls?: ReactNode;
}

export function AntarcticPageHeader({
  title,
  titleHighlight,
  subtitle,
  rightControls,
}: AntarcticPageHeaderProps) {
  return (
    <div className="relative -mx-4 lg:-mx-6 -mt-4 lg:-mt-6 mb-5 lg:mb-6 px-6 lg:px-10 h-[120px] sm:h-[140px] lg:h-[160px] xl:h-[180px] overflow-hidden flex flex-col justify-end pb-3 sm:pb-4 lg:pb-5 xl:pb-6">
      {/* Background Image */}
      <div
        className="absolute inset-0 z-0"
        style={{
          backgroundImage: `url("${bgImage}")`,
          backgroundSize: "cover",
          backgroundPosition: "center center",
          backgroundRepeat: "no-repeat",
          maskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
          WebkitMaskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
        }}
      ></div>

      {/* Subtle Overlay for Readability */}
      <div
        className="absolute inset-0 z-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 70% 70% at 20% 80%, rgba(255,255,255,0.65) 0%, rgba(255,255,255,0) 100%)",
        }}
      ></div>

      {/* Content */}
      <div className="relative z-10 w-full flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="page-title text-2xl sm:text-3xl lg:text-4xl font-black tracking-tight text-navy-900 drop-shadow-sm">
            {title} <span className="text-blue-600">{titleHighlight}</span>
          </h1>
          <p className="text-xs sm:text-sm text-navy-800 font-semibold mt-1 max-w-2xl drop-shadow-sm">
            {subtitle}
          </p>
        </div>

        {rightControls && (
          <div className="flex items-center gap-2 bg-white/75 backdrop-blur-[8px] px-3 py-2 rounded-xl border border-white/50 shadow-sm shrink-0">
            {rightControls}
          </div>
        )}
      </div>
    </div>
  );
}
