// Test-only stand-in for the `@eyra/feldspar` package specifier.
//
// Jest cannot resolve the built package: `@eyra/feldspar`'s exports map
// declares only an "import" (ESM) condition and no "require" one, so the
// CommonJS resolution jest performs for a bare specifier fails outright
// ("Cannot find module '@eyra/feldspar'"). Building the package first would
// not help — the condition, not the artifact, is what is missing.
//
// So `jest.config.js` maps the specifier here and this module re-exports the
// same symbols straight from feldspar *source*. Tests therefore exercise the
// real resolver, not a mock: behaviour asserted here is the behaviour that
// ships. Kept to the modules a `*.test.tsx` actually renders, so the import
// graph stays as small as the test suite needs — the button/prompt UI
// elements below drag in feldspar's icon SVGs, stubbed via jest.config.js's
// `\.svg$` moduleNameMapper entry rather than avoided here.
//
// Add a symbol here only when a `*.test.ts`/`*.test.tsx` needs it.

export { Translator, MISSING_TRANSLATION } from '../../../feldspar/src/framework/translator'
export { default } from '../../../feldspar/src/framework/text_bundle'
export { ReactFactoryContext } from '../../../feldspar/src/framework/visualization/react/factory'
export { BodyLarge, Title4 } from '../../../feldspar/src/framework/visualization/react/ui/elements/text'
export {
  LabelButton,
  PrimaryButton,
} from '../../../feldspar/src/framework/visualization/react/ui/elements/button'
export { DonateButtons } from '../../../feldspar/src/framework/visualization/react/ui/prompts/donate_buttons'
export { ScriptHostComponent } from '../../../feldspar/src/components/script_host_component'
