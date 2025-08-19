interface FooterProps {
  left?: JSX.Element
  middle?: JSX.Element
  right?: JSX.Element
}

export const Footer = ({ left, middle, right }: FooterProps): JSX.Element => {
  return (
    <>
      <div class='bg-grey4 h-px' />
      <div class='h-full flex flex-col justify-center'>
        <div class='flex flex-row gap-4 px-14'>
          <div class='w-1/3'>
            {left}
          </div>
          <div class='w-1/3'>
            {middle}
          </div>
          <div class='w-1/3'>
            {right}
          </div>
        </div>
      </div>
    </>
  )
}
