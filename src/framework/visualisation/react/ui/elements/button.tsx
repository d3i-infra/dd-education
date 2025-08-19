import { Weak } from '../../../../helpers'
import { PropsUIButtonBack, PropsUIButtonForward, PropsUIButtonIcon, PropsUIButtonIconBack, PropsUIButtonIconForward, PropsUIButtonIconLabel, PropsUIButtonLabel, PropsUIButtonPrimary, PropsUIButtonSecundary } from '../../../../types/elements'

import BackSvg from '../../../../../assets/images/back.svg'
import ForwardSvg from '../../../../../assets/images/forward.svg'
import { Spinner } from './spinner'

function spinnerColor (buttonColor: string): string {
  if (buttonColor.includes('bg-tertiary')) {
    return 'dark'
  }
  return 'light'
}

export const PrimaryButton = ({ label, spinning = false, enabled = true, color = 'bg-primary text-white', onClick }: Weak<PropsUIButtonPrimary>): JSX.Element => {
  return (
    <div class='relative min-w-button'>
      <div class={`flex flex-col items-center leading-none font-button text-button rounded ${enabled ? 'cursor-pointer active:shadow-top4px' : ''} ${color}`} onClick={onClick}>
        <div id='confirm-button' class={`pt-15px pb-15px pr-4 pl-4 ${enabled ? 'active:pt-4 active:pb-14px' : ''} ${spinning ? 'opacity-0' : ''}`}>
          {label}
        </div>
      </div>
      <div class={`absolute top-0 h-full w-full flex flex-col justify-center items-center ${spinning ? '' : 'hidden'}`}>
        <div class='w-5 h-5'>
          <Spinner color={spinnerColor(color)} spinning={spinning} />
        </div>
      </div>
    </div>
  )
}

export const SecondaryButton = ({ label, color = 'bg-delete text-delete', onClick }: Weak<PropsUIButtonSecundary>): JSX.Element => {
  return (
    <div class='relative min-w-button'>
      <div class={`flex flex-col items-center active:shadow-top2px border-2 font-button text-button rounded bg-opacity-0 cursor-pointer ${color}`} onClick={onClick}>
        <div class='pt-13px pb-13px pr-4 pl-4 active:pt-14px active:pb-3'>
          {label}
        </div>
      </div>
    </div>
  )
}

export const BackButton = ({ label, onClick }: Weak<PropsUIButtonBack>): JSX.Element => {
  return <IconLabelButton icon={BackSvg} label={label} onClick={onClick} />
}

export const ForwardButton = ({ label, onClick }: Weak<PropsUIButtonForward>): JSX.Element => {
  return <IconLabelButton icon={ForwardSvg} label={label} onClick={onClick} alignment='right' />
}

export const BackIconButton = ({ onClick }: Weak<PropsUIButtonIconBack>): JSX.Element => {
  return <IconButton icon={BackSvg} onClick={onClick} />
}

export const ForwardIconButton = ({ onClick }: Weak<PropsUIButtonIconForward>): JSX.Element => {
  return <IconButton icon={ForwardSvg} onClick={onClick} />
}

export const IconButton = ({ icon, onClick }: Weak<PropsUIButtonIcon>): JSX.Element => {
  return (
    <div class='active:pt-5px active:pb-3px focus:outline-none cursor-pointer w-6 h-6' onClick={onClick}>
      <div class='flex flex-col items-center h-full w-full'>
        <div class='flex-grow' />
        <div>
          <img class='-mt-2px' src={icon} />
        </div>
        <div class='flex-grow' />
      </div>
    </div>
  )
}

export const IconLabelButton = ({ icon, label, color = 'text-grey1', alignment = 'left', onClick }: Weak<PropsUIButtonIconLabel>): JSX.Element => {
  return (
    <div class='pt-1 pb-1 active:pt-5px active:pb-3px rounded bg-opacity-0 focus:outline-none cursor-pointer ' onClick={onClick}>
      <div class='flex items-center'>
        <div class={`${alignment === 'left' ? '' : 'hidden'}`}>
          <img class='mr-2 -mt-2px' src={icon} alt={label} />
        </div>
        <div class='focus:outline-none'>
          <div class='flex flex-col justify-center h-full items-center'>
            <div class={`flex-wrap text-button font-button ${color}`}>
              {label}
            </div>
          </div>
        </div>
        <div class={`${alignment !== 'left' ? '' : 'hidden'}`}>
          <img class='ml-2 -mt-2px' src={icon} alt={label} />
        </div>
      </div>
    </div>
  )
}

export const LabelButton = ({ label, color = 'text-grey1', onClick }: Weak<PropsUIButtonLabel>): JSX.Element => {
  return (
    <div class={`pt-15px pb-15px active:pt-4 active:pb-14px leading-none font-button text-button rounded pr-4 pl-4 cursor-pointer bg-opacity-0 ${color}`} onClick={onClick}>
      <div id='confirm-button' class='flex-wrap'>
        {label}
      </div>
    </div>
  )
}
