import { Command, Response, CommandSystem, CommandUI } from './commands'
import ReactDOM from 'react-dom/client';

export interface ProcessingEngine {
  start: () => void
  commandHandler: CommandHandler
  terminate: () => void
}

export interface VisualisationEngine {
  start: (rootElement: ReactDOM.Root, locale: string) => void
  render: (command: CommandUI) => Promise<Response>
  terminate: () => void
}

export interface Bridge {
  send: (command: CommandSystem) => void
}

export interface CommandHandler {
  onCommand: (command: Command) => Promise<Response>
}
