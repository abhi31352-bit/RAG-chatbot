/** Globals the test environment provides but TypeScript does not know about. */

declare global {
  /**
   * React 18 checks this before routing updates through `act()`. Testing-library
   * sets it, but only when the automatic cleanup path runs, so the setup file
   * sets it explicitly.
   */
  // eslint-disable-next-line no-var
  var IS_REACT_ACT_ENVIRONMENT: boolean | undefined
}

export {}
