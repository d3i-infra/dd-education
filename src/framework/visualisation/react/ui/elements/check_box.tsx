import { PropsUICheckBox } from '../../../../types/elements'
import CheckSvg from '../../../../../assets/images/check.svg'
import CheckActiveSvg from '../../../../../assets/images/check_active.svg'

export const CheckBox = ({ id, selected, size = 'w-6 h-6', onSelect }: PropsUICheckBox): JSX.Element => {
  return (
    <div id={id} class='radio-item flex flex-row gap-3 cursor-pointer' onClick={onSelect}>
      <div class={`flex-shrink-0  ${size}`}>
        <img src={CheckSvg} id={`${id}-off`} class={`w-full h-full ${selected ? 'hidden' : ''}`} />
        <img src={CheckActiveSvg} id={`${id}-on`} class={`w-full h-full ${selected ? '' : 'hidden'}`} />
      </div>
    </div>
  )
}
