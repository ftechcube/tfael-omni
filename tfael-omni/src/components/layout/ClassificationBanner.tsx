import { cn } from '@/lib/utils';

interface ClassificationBannerProps {
  level?: 'UNCLASSIFIED' | 'RESTRICTED' | 'CONFIDENTIAL' | 'SECRET';
}

const levelStyles: Record<string, string> = {
  unclassified: 'bg-accent-olive text-background-deep',
  restricted:   'bg-secondary text-background-deep',
  confidential: 'bg-destructive text-white',
  secret:       'bg-red-600 text-white',
};

export function ClassificationBanner({ level = 'RESTRICTED' }: ClassificationBannerProps) {
  return (
    <div className={cn(
      'text-center font-mono text-2xs font-bold tracking-[0.12em] py-0.5 shrink-0',
      levelStyles[level.toLowerCase()] ?? levelStyles.restricted
    )}>
      {level} // FOUO
    </div>
  );
}
