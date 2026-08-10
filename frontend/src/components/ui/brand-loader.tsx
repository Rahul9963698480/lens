import { cn } from '@/lib/utils'

const BAR_COUNT = 12

/** Brand gradient stops (as CSS variable references), evenly spaced 0 -> 1. */
const GRADIENT_STOPS = [
  'hsl(var(--brand-navy))',
  'hsl(var(--brand-teal))',
  'hsl(var(--brand-orange))',
]

/** Interpolate the brand gradient at position t (0..1) using color-mix. */
function brandColorAt(t: number): string {
  const segments = GRADIENT_STOPS.length - 1
  const scaled = Math.min(Math.max(t, 0), 1) * segments
  const index = Math.min(Math.floor(scaled), segments - 1)
  const localT = scaled - index
  const from = GRADIENT_STOPS[index]
  const to = GRADIENT_STOPS[index + 1]
  return `color-mix(in srgb, ${to} ${localT * 100}%, ${from})`
}

type BrandSpinnerProps = {
  /** Diameter of the spinner in pixels. Defaults to 56. */
  size?: number
  /** Full rotation duration. Defaults to "1.1s". */
  speed?: string
  className?: string
  /** Accessible label announced to screen readers. Defaults to "Loading". */
  label?: string
}

/**
 * Brand loading indicator: a 12-bar circular spinner tinted with the app's
 * brand palette, transitioning from navy through teal to orange.
 *
 * Uses color-mix on the brand CSS variables so it stays on-brand in both
 * light and dark themes.
 */
export function BrandSpinner({
  size = 56,
  speed = '1.1s',
  className,
  label = 'Loading',
}: BrandSpinnerProps) {
  const barWidth = Math.max(2, Math.round(size * 0.09))
  const barHeight = Math.round(size * 0.28)
  const radius = size / 2 - barHeight / 2

  return (
    <span
      role="status"
      aria-label={label}
      className={cn('inline-block animate-spin', className)}
      style={{
        width: size,
        height: size,
        animationDuration: speed,
        animationTimingFunction: 'linear',
      }}
    >
      <span className="relative block h-full w-full">
        {Array.from({ length: BAR_COUNT }).map((_, i) => {
          const t = i / (BAR_COUNT - 1)
          const angle = i * (360 / BAR_COUNT)
          return (
            <span
              key={i}
              className="absolute left-1/2 top-1/2 rounded-full"
              style={{
                width: barWidth,
                height: barHeight,
                backgroundColor: brandColorAt(t),
                transform: `translate(-50%, -50%) rotate(${angle}deg) translateY(-${radius}px)`,
              }}
            />
          )
        })}
      </span>
      <span className="sr-only">{label}</span>
    </span>
  )
}

type BrandLoaderProps = BrandSpinnerProps & {
  /** Optional message shown beneath the spinner. */
  message?: string
  /** Fill the parent and center the spinner. Defaults to true. */
  fullHeight?: boolean
  containerClassName?: string
}

/**
 * Centered loading state built on BrandSpinner, with an optional message.
 * Drop-in replacement for ad-hoc "Loader2 + text" blocks.
 */
export function BrandLoader({
  message,
  fullHeight = true,
  containerClassName,
  size = 56,
  ...spinnerProps
}: BrandLoaderProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3',
        fullHeight && 'min-h-[200px] w-full',
        containerClassName,
      )}
    >
      <BrandSpinner size={size} {...spinnerProps} />
      {message ? (
        <p className="text-sm text-muted-foreground">{message}</p>
      ) : null}
    </div>
  )
}
