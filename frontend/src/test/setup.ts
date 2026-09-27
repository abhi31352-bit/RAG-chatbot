import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// React 18 only routes updates through act() when the environment advertises
// support. Without this, every render logs a warning and state updates land
// outside act, which makes assertions about intermediate state unreliable.
globalThis.IS_REACT_ACT_ENVIRONMENT = true

// Testing-library skips its automatic cleanup when `afterEach` is not a global,
// which is the case here because vitest runs with `globals: false`. Without an
// explicit cleanup every rendered hook stays mounted for the rest of the file:
// subscribers pile up, each store reset in a beforeEach re-renders all of them
// at once, and the suite leaks state between tests.
afterEach(() => {
  cleanup()
})
