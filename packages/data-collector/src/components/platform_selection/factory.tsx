import { PromptFactory, ReactFactoryContext } from "@eyra/feldspar"
import { PlatformSelection, PropsUIPromptPlatformSelection } from "./platform_selection"

export class PlatformSelectionFactory implements PromptFactory {
  create(body: unknown, context: ReactFactoryContext) {
    if (this.isBody(body)) {
      return <PlatformSelection {...body} {...context} />
    }
    return null
  }

  private isBody(body: unknown): body is PropsUIPromptPlatformSelection {
    return (body as PropsUIPromptPlatformSelection).__type__ === "PropsUIPromptPlatformSelection"
  }
}
