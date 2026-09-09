import { readFileSync } from "fs"
import { join } from "path"

// Both stylesheets are Tailwind 4 with one shared `utilities` layer, so the
// later import wins every same-specificity collision. Feldspar's must come
// first, or its bare utilities (.flex-col, .hidden, .p-4, ...) override our
// responsive variants at every width. This is a source-order guard because
// jsdom cannot see the cascade.
test("feldspar's stylesheet is imported before the package's own", () => {
  const source = readFileSync(join(__dirname, "index.tsx"), "utf8")
  const feldspar = source.indexOf('import "@eyra/feldspar/dist/styles.css"')
  const own = source.indexOf('import "./index.css"')
  expect(feldspar).toBeGreaterThan(-1)
  expect(own).toBeGreaterThan(-1)
  expect(feldspar).toBeLessThan(own)
})
