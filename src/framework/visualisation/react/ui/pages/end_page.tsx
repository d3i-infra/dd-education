import { Weak } from '../../../../helpers'
import { PropsUIPageEnd } from '../../../../types/pages'
import { ReactFactoryContext } from '../../factory'
import { Page } from './templates/page'
import TextBundle from '../../../../text_bundle'
import { Translator } from '../../../../translator'
import { BodyLarge, Title1 } from '../elements/text'
import { PrimaryButton } from '../elements/button'

type Props = Weak<PropsUIPageEnd> & ReactFactoryContext

export const EndPage = (props: Props): JSX.Element => {
  const { title, text } = prepareCopy(props)
  const { resolve } = props

  function handleClick(): void {
    //const value = serializeConsentData()
    const value = ""
    resolve?.({ __type__: "PayloadJSON", value })
  }


  const body: JSX.Element = (
    <>
      <Title1 text={title} />
      <BodyLarge text={text} />
    </>
  )

  return (
    <>
    <Page
      body={body}
    />
  <div class="flex flex-row gap-4">
    <PrimaryButton
      label="Restart"
      onClick={handleClick}
      color="bg-success text-white"
      spinning={false}
    />
  </div>
</>
  )
}

interface Copy {
  title: string
  text: string
}

function prepareCopy ({ locale }: Props): Copy {
  return {
    title: Translator.translate(title, locale),
    text: Translator.translate(text, locale)
  }
}

const title = new TextBundle()
  .add('en', 'Thank you')
  .add('nl', 'Bedankt')

const text = new TextBundle()
  .add('en', 'We hoped you enjoyed exploring your data! Click the restart button to start again.')
  .add('nl', 'We hoped you enjoyed exploring your data! Click the restart button to start again.')
