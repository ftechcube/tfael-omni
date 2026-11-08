import { useApp } from '@/context/AppContext';

export function StatusBar() {
  const { overview, utcTime } = useApp();

  const serverVer = 'TFAEL-OMNI v2.0';
  const unitCount = overview?.units?.length ?? 0;
  const targetCount = overview?.targets?.length ?? 0;

  return (
    <footer className="flex items-center gap-2 h-6 px-3 bg-background-deep border-t border-border-dim font-mono text-2xs text-foreground-muted opacity-60 shrink-0">
      <span className="whitespace-nowrap">{serverVer}</span>
      <span className="opacity-30">|</span>
      <span className="whitespace-nowrap">Targets: {targetCount}</span>
      <span className="opacity-30">|</span>
      <span className="whitespace-nowrap">Units: {unitCount}</span>
      <span className="flex-1" />
      <span className="whitespace-nowrap">{utcTime}</span>
    </footer>
  );
}
