// jsdom (jest's jsdom test environment included) does not implement
// TextEncoder/TextDecoder — see https://github.com/jsdom/jsdom/issues/2524.
// react-router-dom's data routers (createMemoryRouter, createHashRouter) pull
// in "turbo-stream", which needs TextEncoder at module load time, so any test
// that imports react-router-dom under `/** @jest-environment jsdom */` fails
// before a single test runs unless this is filled in first. Node's own `util`
// already implements both; this just makes them global the way a browser
// would. A no-op under the `node` test environment, where Node's globals
// already have them.
import { TextDecoder, TextEncoder } from "util"

if (typeof globalThis.TextEncoder === "undefined") {
  ;(globalThis as unknown as { TextEncoder: typeof TextEncoder }).TextEncoder = TextEncoder
}
if (typeof globalThis.TextDecoder === "undefined") {
  ;(globalThis as unknown as { TextDecoder: typeof TextDecoder }).TextDecoder = TextDecoder
}
