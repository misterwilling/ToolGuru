// Pure utility functions — no React, no DOM, no bridge. Everything that
// doesn't need a browser goes here so it's directly testable with Vitest.

export function formatSlot(slot: string): string {
  return slot.charAt(0).toUpperCase() + slot.slice(1).replace(/_/g, ' ')
}
