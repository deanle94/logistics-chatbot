/**
 * The two series colours of `docs/design/Main.dc.html`.
 *
 * They live here rather than in `index.css` because the project's `--chart-1..5` tokens are
 * the greyscale ramp of the installed shadcn style, and every other Slice 0 surface depends
 * on that theme. Two named constants keep the design's palette out of three chart files
 * without repainting a global token that something else might be using tomorrow.
 */

/** Delivered / on-time - the calm series. */
export const COLOR_ON_TIME = 'oklch(0.6 0.118 184.704)'

/** Delayed, and the single-series charts - the series the manager is looking for. */
export const COLOR_ATTENTION = 'oklch(0.646 0.222 41.116)'
