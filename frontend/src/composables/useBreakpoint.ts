/**
 * useBreakpoint(): compact (< 600) · medium (600–1023) · expanded (≥ 1024), με matchMedia (όχι user-agent).
 * Τα όρια είναι τα ίδια με τα media queries του CSS (styles/tokens.css, ενότητα breakpoints). Μοιραζόμενο state:
 * ένας listener για όλη την εφαρμογή.
 */
import { computed, ref } from 'vue'

export type Breakpoint = 'compact' | 'medium' | 'expanded'
export const BP_MEDIUM = 600
export const BP_EXPANDED = 1024

const name = ref<Breakpoint>('compact')
let installed = false

function install(): void {
  if (installed || typeof window === 'undefined' || !window.matchMedia) return
  installed = true
  const medium = window.matchMedia(`(min-width: ${BP_MEDIUM}px)`)
  const expanded = window.matchMedia(`(min-width: ${BP_EXPANDED}px)`)
  const update = (): void => { name.value = expanded.matches ? 'expanded' : medium.matches ? 'medium' : 'compact' }
  medium.addEventListener('change', update)
  expanded.addEventListener('change', update)
  update()
}

export function useBreakpoint() {
  install()
  return {
    name,
    isCompact: computed(() => name.value === 'compact'),
    isMedium: computed(() => name.value === 'medium'),
    isExpanded: computed(() => name.value === 'expanded'),
  }
}
