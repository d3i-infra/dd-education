// Jest stub for `*.png`/`*.jpg`/`*.jpeg` imports (a URL string Vite produces at build
// time but Jest cannot parse as a module — the raw binary is not valid JS). Needed to
// render the site footer under jsdom, which imports its funder logos at module scope.
// See jest.config.js moduleNameMapper.
module.exports = "image-stub"
