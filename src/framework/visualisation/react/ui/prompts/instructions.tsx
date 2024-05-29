import { Weak } from '../../../../helpers'
import * as React from 'react'
import { Translatable } from '../../../../types/elements'
import TextBundle from '../../../../text_bundle'
import { Translator } from '../../../../translator'
import { ReactFactoryContext } from '../../factory'
import { PropsUIPromptInstructions } from '../../../../types/prompts'
import { PrimaryButton } from '../elements/button'

type Props = Weak<PropsUIPromptInstructions> & ReactFactoryContext

export const Instructions = (props: Props): JSX.Element => {
  const [waiting, setWaiting] = React.useState<boolean>(false)

  React.useEffect(() => {
    // check if running in an iframe
    if (window.frameElement) {
      window.parent.scrollTo(0,0)
    } else {
      window.scrollTo(0,0)
    }
  }, [])


  const { imageUrl, resolve } = props
  const { description, continueButton } = prepareCopy(props)

  function handleConfirm (): void {
      if (!waiting) {
        setWaiting(true)
        resolve?.({ __type__: 'PayloadString', value: "continue" })
      }
    }

  return (
    <>
      <div id='select-panel'>
        <div className='flex-wrap text-bodylarge font-body text-grey1 text-left'>
          {description}
        </div>
      </div>
      <div className='flex items-center justify-center min-h-screen bg-gray-100'>
        <img src={imageUrl} alt='Instructions' className='max-w-s'></img>
      </div>
      <div className='mt-8' />
      <div className='flex flex-row gap-4'>
        <PrimaryButton label={continueButton} onClick={handleConfirm} enabled={true} spinning={waiting} />
      </div>
    </>
  )
}

interface Copy {
  description: string
  continueButton: string
}

function prepareCopy ({ description, locale }: Props): Copy {
  return {
    description: Translator.translate(description, locale),
    continueButton: Translator.translate(continueButtonLabel(), locale),
  }
}

const continueButtonLabel = (): Translatable => {
  return new TextBundle()
    .add('en', 'Continue')
    .add('nl', 'Doorgaan')
}
