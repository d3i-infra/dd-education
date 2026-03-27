import { PromptFactory, ReactFactoryContext } from "@eyra/feldspar"
import { Instructions, PropsUIPromptInstructions } from "./instructions"

export class InstructionsFactory implements PromptFactory {
  create(body: unknown, context: ReactFactoryContext) {
    if (this.isBody(body)) {
      return <Instructions {...body} {...context} />
    }
    return null
  }

  private isBody(body: unknown): body is PropsUIPromptInstructions {
    return (body as PropsUIPromptInstructions).__type__ === "PropsUIPromptInstructions"
  }
}
