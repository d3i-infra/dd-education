import { PropsUIRadioItem } from '../../../../types/elements'
import RadioSvg from '../../../../../assets/images/radio.svg'
import RadioActiveSvg from '../../../../../assets/images/radio_active.svg'

export const RadioItem = ({ id, value, selected, onSelect }: PropsUIRadioItem): JSX.Element => {
  return (
    <div id={`${id}`} class='radio-item flex flex-row gap-3 items-center cursor-pointer' onClick={onSelect}>
      <div>
        <img src={RadioSvg} id={`${id}-off`} class={selected ? 'hidden' : ''} />
        <img src={RadioActiveSvg} id={`${id}-on`} class={selected ? '' : 'hidden'} />
      </div>
      <div class='text-grey1 text-label font-label select-none mt-1'>
        {value}
      </div>
    </div>
  )
}
