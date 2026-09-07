import { PlatformSelectionFactory } from "./platform_selection/factory"
import { InstructionsFactory } from "./instructions/factory"
import { IssueFormFactory } from "./issue_form/factory"

const context = { locale: "en", resolve: () => {} } as any

test.each([
  [new PlatformSelectionFactory(), "PropsUIPromptPlatformSelection"],
  [new InstructionsFactory(), "PropsUIPromptInstructions"],
  [new IssueFormFactory(), "PropsUIPromptIssueForm"],
])("%s creates an element only for its own __type__", (factory, type) => {
  expect(factory.create({ __type__: type }, context)).not.toBeNull()
  expect(factory.create({ __type__: "PropsUIPromptConfirm" }, context)).toBeNull()
})
