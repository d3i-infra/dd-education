import React, { useEffect } from 'react';
import ReactDOM from 'react-dom/client';
import Assembly from '../framework/assembly'
import { Bridge } from '../framework/types/modules'
import FakeBridge from '../fake_bridge'


const ReactEngineComponent = ({root, locale }: { root: ReactDOM.Root, locale: string }) => {
  useEffect(() => {

    const workerFile = new URL('../framework/processing/py_worker.js', import.meta.url)
    const worker = new Worker(workerFile)

    let assembly: Assembly

    const run = (bridge: Bridge, locale: string): void => {
      assembly = new Assembly(worker, bridge)
      assembly.visualisationEngine.start(root, locale)
      assembly.processingEngine.start()
    }

    // We only need fake bridge check eyra/feldspar for the details
    console.log('Running with fake bridge')
    run(new FakeBridge(), 'en')

  }, [locale]);

  return <div id="react-engine-root"></div>;
};

export default ReactEngineComponent;

