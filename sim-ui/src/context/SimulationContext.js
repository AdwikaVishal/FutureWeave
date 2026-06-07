import React, { createContext, useContext, useState, useCallback } from 'react';
import { simulateV2 as apiSimulate } from '../api';

const SimulationContext = createContext(null);

export function SimulationProvider({ children }) {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [decision, setDecision] = useState('');
  const [context, setContext] = useState({});

  const runSimulation = useCallback(async (dec, ctx) => {
    setLoading(true);
    setError(null);
    setResult(null);
    setDecision(dec);
    const simContext = ctx;
    setContext(simContext);
    try {
      const data = await apiSimulate(dec, simContext, false, 0);
      setResult(data);
    } catch (err) {
      setError(err.message || 'Simulation failed.');
    }
    setLoading(false);
  }, []);

  const reset = useCallback(() => {
    setResult(null);
    setDecision('');
    setError(null);
  }, []);

  return (
    <SimulationContext.Provider value={{
      result, loading, error, decision, context,
      runSimulation, reset, setError,
    }}>
      {children}
    </SimulationContext.Provider>
  );
}

export function useSim() {
  const ctx = useContext(SimulationContext);
  if (!ctx) throw new Error('useSim must be inside SimulationProvider');
  return ctx;
}
