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
}

type Props = PropsUIPromptInstructions & ReactFactoryContext

export const Instructions = (props: Props): JSX.Element => {
  const [waiting, setWaiting] = useState<boolean>(false)
  const { imageUrl, resolve, locale } = props
  const description = Translator.translate(props.description, locale)
  const continueButton = Translator.translate(continueButtonLabel, locale)

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "auto" })
  }, [])

  function handleConfirm(): void {
    if (!waiting) {
      setWaiting(true)
      resolve?.({ __type__: "PayloadString", value: "continue" })
    }
  }

  return (
    <>
      <div id="select-panel">
        <div className="flex-wrap text-bodylarge font-body text-grey1 text-left">
          {description}
        </div>
      </div>
      {imageUrl && (
        <div className="flex items-center justify-center my-8">
          <img src={imageUrl} alt="Instructions" className="max-w-full" />
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
