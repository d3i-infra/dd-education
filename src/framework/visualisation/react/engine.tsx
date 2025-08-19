import ReactDOM from 'react-dom/client';
import { VisualisationEngine } from '../../types/modules'
import { Response, Payload, CommandUIRender } from '../../types/commands'
import { PropsUIPage } from '../../types/pages'
import VisualisationFactory from './factory'
import { Main } from './main'
import { Spinner } from './ui/elements/spinner'

export default class ReactEngine implements VisualisationEngine {
  factory: VisualisationFactory

  locale!: string
  root!: ReactDOM.Root

  constructor (factory: VisualisationFactory) {
    this.factory = factory
  }

  start (rootElement: ReactDOM.Root, locale: string): void {

    console.log('[ReactEngine] started')
    this.root = rootElement
    this.root.render(<LoadingScreen />)
    this.locale = locale
  }

  async render (command: CommandUIRender): Promise<Response> {
    return await new Promise<Response>((resolve) => {
      this.renderPage(command.page).then(
        (payload: Payload) => {
          resolve({ __type__: 'Response', command, payload })
        },
        () => {}
      )
    })
  }

  async renderPage (props: PropsUIPage): Promise<any> {
    return await new Promise<any>((resolve) => {
      const context = { locale: this.locale, resolve }
      const page = this.factory.createPage(props, context)
      this.renderElements([page])
    })
  }

  terminate (): void {
    console.log('[ReactEngine] stopped')
    this.root.unmount()
  }

  renderElements (elements: JSX.Element[]): void {
    this.root.render(<Main elements={elements} />)
  }
}

const LoadingScreen = () => {
  return (
    <div>
     <div class="flex items-center justify-center min-h-screen bg-gray-100">
      <div class="text-center">
        <Spinner color="dark" spinning={true} size="full" />
        <p class="mt-4 text-xl font-semibold text-gray-700">Loading...</p>
        <div class="mt-4 p-2 bg-gray-200 text-left text-sm text-gray-600 rounded-lg shadow-inner max-w-md mx-auto">
          <pre id="consoleOutput">Please hold on for a couple of seconds...</pre>
        </div>
      </div>
    </div>
    </div>
  );
};

