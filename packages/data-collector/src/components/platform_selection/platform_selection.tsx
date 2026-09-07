import { useState } from "react"
import { JSX } from "react"
import { PrimaryButton, ReactFactoryContext, Translator } from "@eyra/feldspar"

interface Translatable {
  translations: Record<string, string>
}

export interface PropsUIPromptPlatformSelection {
  __type__: "PropsUIPromptPlatformSelection"
  title: Translatable
  intro: Translatable
  instructions: Translatable[]
  footer: Translatable
  items: { id: number; value: string }[]
  continueLabel: Translatable
}

type Props = PropsUIPromptPlatformSelection & ReactFactoryContext

export function PlatformSelection({
  title,
  intro,
  instructions,
  footer,
  items,
  continueLabel,
  locale,
  resolve,
}: Props): JSX.Element {
  const [selectedItem, setSelectedItem] = useState<{ id: number; value: string } | null>(null)

  const translatedTitle = Translator.translate(title, locale)
  const translatedIntro = Translator.translate(intro, locale)
  const translatedInstructions = instructions.map((instr) => Translator.translate(instr, locale))
  const translatedFooter = Translator.translate(footer, locale)
  const translatedContinueLabel = Translator.translate(continueLabel, locale)

  function handleConfirm(): void {
    if (selectedItem !== null) {
      resolve?.({ __type__: "PayloadString", value: selectedItem.value })
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <p className="text-bodylarge font-body text-grey1">{translatedIntro}</p>

      <ul className="flex flex-col gap-2 pl-6 list-disc">
        {translatedInstructions.map((instr, i) => (
          <li key={i} className="text-bodylarge font-body text-grey1">
            {instr}
          </li>
        ))}
      </ul>

      <p className="text-bodylarge font-body text-grey1">{translatedFooter}</p>

      <fieldset className="border-0 p-0 m-0">
        <legend className="text-title5 font-title5 sm:text-title4 sm:font-title4 text-grey1 mb-4">
          {translatedTitle}
        </legend>
        <div className="flex flex-col gap-3">
          {items.map((item) => (
            <label
              key={item.id}
              className="flex flex-row gap-3 items-center cursor-pointer text-grey1 text-label font-label select-none"
            >
              <input
                type="radio"
                name="platform"
                value={item.value}
                checked={selectedItem?.id === item.id}
                onChange={() => setSelectedItem(item)}
                className="accent-primary"
              />
              {item.value}
            </label>
          ))}
        </div>
      </fieldset>

      <div className={`flex flex-row gap-4 ${selectedItem !== null ? "" : "opacity-30"}`}>
        <PrimaryButton
          label={translatedContinueLabel}
          onClick={handleConfirm}
          enabled={selectedItem !== null}
        />
      </div>
    </div>
  )
}
