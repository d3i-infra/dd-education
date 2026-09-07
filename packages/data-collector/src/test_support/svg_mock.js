// Jest stub for `*.svg` imports (an inline-XML default export Vite handles at
// build time but Jest cannot parse as a module). Needed to render feldspar's
// button.tsx under jsdom — it imports icon SVGs at module scope even when a
// test only exercises a text-label button (PrimaryButton, LabelButton) that
// never uses them. See jest.config.js moduleNameMapper.
module.exports = "svg-stub"
