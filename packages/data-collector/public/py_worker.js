let pyScript;

console.log("[ProcessingWorker] Worker loaded");

onmessage = (event) => {
  console.log("[ProcessingWorker] Received event: ", event.data);
  const { eventType } = event.data;
  switch (eventType) {
    case "initialise":
      initialise().then(() => {
        self.postMessage({ eventType: "initialiseDone" });
      });
      break;

    case "firstRunCycle": {
      const ctx = event.data.data;
      // strip null/undefined/"undefined": the JSON text is interpolated as a Python
      // literal and values must stay strings/numbers (JSON null is not Python)
      for (const k of Object.keys(ctx)) if (ctx[k] == null || ctx[k] === "undefined") delete ctx[k];
      pyScript = self.pyodide.runPython(`port.start(${JSON.stringify(ctx)})`);
      runCycle(null);
      break;
    }

    case "nextRunCycle":
      const { response } = event.data;
      unwrap(response).then((userInput) => {
        runCycle(userInput);
      });
      break;

    default:
      console.log("[ProcessingWorker] Received unsupported event: ", eventType);
  }
};

function runCycle(payload) {
  console.log("[ProcessingWorker] runCycle " + JSON.stringify(payload));
  let scriptEvent;
  try {
    scriptEvent = pyScript.send(payload);
  } catch (error) {
    // Local diagnostics only — escaped Python errors reach the participant
    // as a rendered error page (ADR-0022); never posted as error/log events
    // that would forward unconsented traceback text (ADR-0023).
    console.error("[ProcessingWorker] Error in pyScript.send:", error);
    self.postMessage({
      eventType: "runCycleDone",
      scriptEvent: generateErrorMessage(String(error)),
    });
    return;
  }
  try {
    self.postMessage({
      eventType: "runCycleDone",
      scriptEvent: scriptEvent.toJs({
        create_proxies: false,
        dict_converter: Object.fromEntries,
      }),
    });
  } catch (error) {
    console.error("[ProcessingWorker] Error in toJs/postMessage:", error);
    self.postMessage({
      eventType: "runCycleDone",
      scriptEvent: generateErrorMessage(String(error)),
    });
  }
}

function generateErrorMessage(message) {
  return {
    __type__: "CommandUIRender",
    page: {
      __type__: "PropsUIPageDataSubmission",
      platform: "error",
      header: {
        __type__: "PropsUIHeader",
        title: { translations: { nl: "Er is iets misgegaan", en: "Something went wrong" } },
      },
      body: [
        {
          __type__: "PropsUIPageError",
          message: message,
        },
      ],
    },
  };
}

function unwrap(response) {
  console.log(
    "[ProcessingWorker] unwrap response: " + JSON.stringify(response.payload)
  );
  return new Promise((resolve) => {
    switch (response.payload.__type__) {
      case "PayloadFile":
        copyFileToPyFS(response.payload.value, resolve);
        break;

      case "PayloadFiles":
        resolve({
          __type__: "PayloadFiles",
          value: response.payload.value.map(createAsyncFileReader),
        });
        break;

      default:
        resolve(response.payload);
    }
  });
}

function createAsyncFileReader(file) {
  // Use FileReaderSync for synchronous reading in worker
  const fileReaderSync = new FileReaderSync();

  return {
    readSlice: (start, end) => {
      // Synchronous slice reading
      const blob = file.slice(start, end);
      return fileReaderSync.readAsArrayBuffer(blob);
    },
    size: file.size,
    name: file.name,
  };
}

function copyFileToPyFS(file, resolve) {
  const reader = createAsyncFileReader(file);
  resolve({
    __type__: "PayloadFile",
    value: reader,
  });
}

function initialise() {
  console.log("[ProcessingWorker] initialise");
  return startPyodide()
    .then((pyodide) => {
      self.pyodide = pyodide;
      return loadPackages();
    })
    .then(() => {
      return installPortPackage();
    });
}

function startPyodide() {
  importScripts("https://cdn.jsdelivr.net/pyodide/v0.24.0/full/pyodide.js");

  console.log("[ProcessingWorker] loading Pyodide");
  return loadPyodide({
    indexURL: "https://cdn.jsdelivr.net/pyodide/v0.24.0/full/",
  });
}

function loadPackages() {
  console.log("[ProcessingWorker] loading packages");
  // "tzdata" is not in Pyodide 0.24's bundled package index, so it cannot be loaded here;
  // installPortPackage() fetches it from PyPI through micropip instead.
  return self.pyodide.loadPackage(["micropip", "numpy", "pandas", "lxml"]);
}

async function installPortPackage() {
  console.log("[ProcessingWorker] load port package");
  // Pyodide 0.24 ships no IANA timezone database, and "tzdata" is not in its bundled
  // package index either, so it comes from PyPI as a pure-Python wheel (~350 KB). Without
  // it `zoneinfo` cannot resolve Europe/Amsterdam and the Python side writes every
  // timestamp in UTC instead (extraction_helpers._reference_zone falls back and warns
  // locally). That is a degraded result, not a broken one, so a failed install must never
  // block boot — hence the catch.
  try {
    await self.pyodide.runPythonAsync(`
      import micropip
      await micropip.install("tzdata")
    `);
  } catch (e) {
    console.warn("tzdata unavailable, timestamps fall back to UTC", e);
  }
  return self.pyodide.runPythonAsync(`
    import micropip
    await micropip.install("./port-0.0.0-py3-none-any.whl", deps=False)
    import port
  `);
}
