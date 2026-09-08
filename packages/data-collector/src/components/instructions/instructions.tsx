import {
  PrimaryButton,
  Translator,
  ReactFactoryContext,
} from "@eyra/feldspar"
import TextBundle from "@eyra/feldspar"
import { useEffect, useState, JSX } from "react"

export interface PropsUIPromptInstructions {
  __type__: "PropsUIPromptInstructions"
  description: { translations: Record<string, string> }
  imageUrl: string
  imageUrls?: string[]
}

type Props = PropsUIPromptInstructions & ReactFactoryContext

export const Instructions = (props: Props): JSX.Element => {
  const [waiting, setWaiting] = useState<boolean>(false)
  const { imageUrl, imageUrls, resolve, locale } = props
  const description = Translator.translate(props.description, locale)
  const continueButton = Translator.translate(continueButtonLabel, locale)

  // A deck of more than one step renders the stepper; a single image (or a
  // deck with exactly one step) keeps the original single-image behaviour.
  const steps = imageUrls !== undefined && imageUrls.length > 1 ? imageUrls : undefined
  const [stepIndex, setStepIndex] = useState<number>(0)

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "auto" })
  }, [])

  useEffect(() => {
    if (steps === undefined) return
    const stepCount = steps.length
    function handleKeyDown(event: KeyboardEvent): void {
      if (event.key === "ArrowRight") {
        setStepIndex((i) => Math.min(i + 1, stepCount - 1))
      } else if (event.key === "ArrowLeft") {
        setStepIndex((i) => Math.max(i - 1, 0))
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [steps])

  function handleConfirm(): void {
    if (!waiting) {
      setWaiting(true)
      resolve?.({ __type__: "PayloadString", value: "continue" })
    }
  }

  // Falls back to imageUrls[0] for a one-entry deck, whose imageUrl is left
  // empty by render_instructions_page (port_helpers.py) — still a single
  // image, just sent through the list field.
  const singleImageUrl = imageUrl !== "" ? imageUrl : (imageUrls?.[0] ?? "")
  const currentImageUrl = steps !== undefined ? steps[stepIndex] : singleImageUrl
  const nextImageUrl = steps !== undefined && stepIndex + 1 < steps.length ? steps[stepIndex + 1] : undefined

  // Prefetch the next step's image via a detached Image so Next never shows
  // a blank frame — a hidden <img> in the DOM would not actually defer to
  // this, since browsers do not lazy-load boxless (display:none) images.
  useEffect(() => {
    if (nextImageUrl === undefined) return
    const preload = new Image()
    preload.src = nextImageUrl
  }, [nextImageUrl])

  return (
    <>
      <div id="select-panel">
        <div className="flex-wrap text-bodylarge font-body text-grey1 text-left whitespace-pre-line">
          {description}
        </div>
      </div>
      {steps !== undefined && (
        <div className="mt-4 text-center text-label font-label text-grey1" aria-live="polite" aria-atomic="true">
          {Translator.translate(stepLabel(stepIndex + 1, steps.length), locale)}
        </div>
      )}
      {currentImageUrl && (
        <div className="flex items-center justify-center my-8">
          <img src={currentImageUrl} alt={steps !== undefined ? `Step ${stepIndex + 1}` : "Instructions"} className="max-w-full" />
        </div>
      )}
      {steps !== undefined && (
        <div className="flex flex-col items-center gap-3 mb-8">
          <div className="flex flex-row gap-3">
            <button
              type="button"
              onClick={() => setStepIndex((i) => Math.max(i - 1, 0))}
              disabled={stepIndex === 0}
              className="rounded-full border-2 border-grey4 text-grey1 font-label text-label px-4 py-2 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {Translator.translate(previousLabel, locale)}
            </button>
            <button
              type="button"
              onClick={() => setStepIndex((i) => Math.min(i + 1, steps.length - 1))}
              disabled={stepIndex === steps.length - 1}
              className="rounded-full border-2 border-primary bg-primarylight text-primary font-label text-label px-4 py-2 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {Translator.translate(nextLabel, locale)}
            </button>
          </div>
          <div className="flex flex-row gap-2">
            {steps.map((_, i) => (
              <button
                key={i}
                type="button"
                aria-label={`Step ${i + 1}`}
                aria-current={i === stepIndex ? "true" : undefined}
                onClick={() => setStepIndex(i)}
                className={`w-2.5 h-2.5 rounded-full ${i === stepIndex ? "bg-primary" : "bg-grey4"}`}
              />
            ))}
          </div>
        </div>
      )}
      <div className="mt-8" />
      <div className="flex flex-row gap-4">
        <PrimaryButton label={continueButton} onClick={handleConfirm} spinning={waiting} />
      </div>
    </>
  )
}

const continueButtonLabel = new TextBundle()
  .add("en", "Continue")
  .add("nl", "Doorgaan")

const previousLabel = new TextBundle()
  .add("en", "Previous")
  .add("nl", "Vorige")

const nextLabel = new TextBundle()
  .add("en", "Next")
  .add("nl", "Volgende")

function stepLabel(step: number, total: number): TextBundle {
  return new TextBundle()
    .add("en", `Step ${step} of ${total}`)
    .add("nl", `Stap ${step} van ${total}`)
}
