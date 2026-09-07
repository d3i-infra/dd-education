import { PromptFactory, ReactFactoryContext } from "@eyra/feldspar"
import { IssueForm } from "./issue_form"
import { PropsUIPromptIssueForm } from "./types"

export class IssueFormFactory implements PromptFactory {
  create(body: unknown, context: ReactFactoryContext) {
    if (this.isBody(body)) {
      return <IssueForm {...body} {...context} />
    }
    return null
  }

  private isBody(body: unknown): body is PropsUIPromptIssueForm {
    return (body as PropsUIPromptIssueForm).__type__ === "PropsUIPromptIssueForm"
  }
}
