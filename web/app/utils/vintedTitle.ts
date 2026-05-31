/** Vinted: at most 3 consecutive uppercase letters (e.g. VSTAR is invalid). */
const VINTED_TITLE_UPPERCASE_RUN_TEST_RE = /\p{Lu}{4,}/u
const VINTED_TITLE_UPPERCASE_RUN_REPLACE_RE = /\p{Lu}{4,}/gu

/**
 * Normalize uppercase runs of 4+ letters for Vinted (e.g. VSTAR → Vstar, VMAX → Vmax).
 * Shorter runs (PSA, EX, NM) are left unchanged.
 * @param text - Raw title from scan, market, or catalog prefill.
 * @returns Title safe for Vinted consecutive-uppercase rule.
 */
export function normalizeVintedTitleUppercaseRuns(text: string): string {
  return text.replace(VINTED_TITLE_UPPERCASE_RUN_REPLACE_RE, (run) => run.charAt(0) + run.slice(1).toLowerCase())
}

/**
 * Whether the title satisfies Vinted's consecutive-uppercase limit.
 * @param text - Title to validate.
 * @returns True when no run of 4+ uppercase letters remains.
 */
export function titleWithinVintedUppercaseRunRule(text: string): boolean {
  return !VINTED_TITLE_UPPERCASE_RUN_TEST_RE.test(text.trim())
}
