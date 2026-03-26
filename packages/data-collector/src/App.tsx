import { DataSubmissionPageFactory, ScriptHostComponent } from "@eyra/feldspar";
import { ConsentFormVizFactory } from "./factories/consent_form_viz";
import { FileInputMultipleFactory } from "./components/file_input_multiple/factory"
import { ErrorPageFactory } from "./components/error_page/factory"
import { QuestionnaireFactory } from "./components/questionnaire/factory"
import { RetryPromptFactory } from "./components/retry_prompt/factory"
import { IssueFormFactory } from "./components/issue_form/factory"
import { PlatformSelectionFactory } from "./components/platform_selection/factory"

function App() {
  return (
    <div className="App">
      <ScriptHostComponent
        workerUrl="./py_worker.js"
        standalone={import.meta.env.DEV}
        logLevel={import.meta.env.DEV ? "debug" : "info"}
        factories={[
          new DataSubmissionPageFactory({
            promptFactories: [
                new ConsentFormVizFactory(),
                new FileInputMultipleFactory(),
                new ErrorPageFactory(),
                new QuestionnaireFactory(),
                new RetryPromptFactory(),
                new IssueFormFactory(),
                new PlatformSelectionFactory(),
            ],
          }),
        ]}
      />
    </div>
  );
}

export default App;
