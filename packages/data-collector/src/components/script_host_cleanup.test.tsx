/** @jest-environment jsdom */
import { act, StrictMode } from "react"
import { createRoot, type Root } from "react-dom/client"

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

import { ScriptHostComponent } from "@eyra/feldspar"

// A Worker stand-in that records every instance and its terminate() calls.
class FakeWorker {
  static instances: FakeWorker[] = []
  terminated = 0
  onmessage: ((e: MessageEvent) => void) | null = null
  onerror: ((e: ErrorEvent) => void) | null = null
  constructor (public url: string) { FakeWorker.instances.push(this) }
  postMessage (): void {}
  addEventListener (): void {}
  removeEventListener (): void {}
  terminate (): void { this.terminated += 1 }
}

let container: HTMLDivElement
let root: Root

beforeEach(() => {
  FakeWorker.instances = []
  ;(globalThis as any).Worker = FakeWorker
  ;(globalThis as any).ResizeObserver = class { observe (): void {} disconnect (): void {} }
  container = document.createElement("div")
  document.body.appendChild(container)
})

afterEach(() => {
  container.remove()
})

test("a StrictMode double mount terminates the first worker and keeps the second", async () => {
  root = createRoot(container)
  act(() => {
    root.render(
      <StrictMode>
        <ScriptHostComponent workerUrl="fake-worker.js" standalone />
      </StrictMode>
    )
  })
  // The cleanup defers its terminate() by one macrotask.
  await new Promise((resolve) => setTimeout(resolve, 10))
  expect(FakeWorker.instances).toHaveLength(2)
  expect(FakeWorker.instances[0].terminated).toBe(1)
  expect(FakeWorker.instances[1].terminated).toBe(0)
  act(() => {
    root.unmount()
  })
})

test("unmounting terminates the live worker exactly once", async () => {
  root = createRoot(container)
  act(() => {
    root.render(<ScriptHostComponent workerUrl="fake-worker.js" standalone />)
  })
  act(() => {
    root.unmount()
  })
  await new Promise((resolve) => setTimeout(resolve, 10))
  expect(FakeWorker.instances).toHaveLength(1)
  expect(FakeWorker.instances[0].terminated).toBe(1)
})
