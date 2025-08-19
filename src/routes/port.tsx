import React, { useEffect, useRef } from 'react';
import ReactDOM from 'react-dom/client';
import Assembly from '../framework/assembly'
import { Bridge } from '../framework/types/modules'
import FakeBridge from '../fake_bridge'



const Port = ({ root, locale }: { root: ReactDOM.Root, locale: string }) => {
  const workerRef = useRef<Worker | null>(null);
  const assemblyRef = useRef<Assembly | null>(null);

  useEffect(() => {
    if (!workerRef.current) {
      const workerFile = new URL('../framework/processing/py_worker.js', import.meta.url);
      workerRef.current = new Worker(workerFile);
      
      // Pass only the URL to the worker
      const portUrl = import.meta.env.VITE_PORT_URL || "https://d3i-infra.github.io/dd-education/port-0.0.0-py3-none-any.whl"
      
      workerRef.current.postMessage({
        eventType: 'sendPortUrl',
        portUrl: portUrl
      })
    }

    const run = (bridge: Bridge, locale: string): void => {
      if (!assemblyRef.current) {
        assemblyRef.current = new Assembly(workerRef.current!, bridge);
      }
      assemblyRef.current.visualisationEngine.start(root, locale);
      assemblyRef.current.processingEngine.start();
    };

    // We only need fake bridge check eyra/feldspar for the details
    console.log('Running with fake bridge');
    run(new FakeBridge(), locale);

    // Cleanup function
    return () => {
      if (assemblyRef.current) {
        // Add any cleanup code here if needed
        // For example: assemblyRef.current.cleanup();
      }
    };
  }, [locale]); // Only locale in the dependencies array

  return <div id="react-engine-root"></div>;
};

export default Port;
