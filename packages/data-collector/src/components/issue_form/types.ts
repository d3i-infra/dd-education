import { PropsUIPromptConsentFormTableViz, Text } from "../consent_form_viz/types"

export interface PropsUIPromptIssueForm {
  __type__: "PropsUIPromptIssueForm"
  description: Text
  tables: PropsUIPromptConsentFormTableViz[]
  platform: string
}
