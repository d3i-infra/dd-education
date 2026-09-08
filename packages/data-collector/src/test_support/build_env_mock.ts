/**
 * Stands in for `src/build_env.ts` under Jest, which cannot parse `import.meta`.
 *
 * Starts empty — the state of a build that configured nothing, which is what most tests
 * want to assert about. A test that needs a configured build writes onto this object and
 * clears it again afterwards.
 */
import type { BuildEnv } from "../build_env"

export const buildEnv: BuildEnv = {}
