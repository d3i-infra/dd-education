interface PageProps {
  body: JSX.Element
  footer?: JSX.Element
}

export const Page = (props: PageProps): JSX.Element => {
  return (
    <div class='w-full h-full'>
      {props.body}
      {props.footer != null && (
        <div class='h-footer flex-shrink-0 mt-5'>{props.footer}</div>
      )}
    </div>
  )
}
