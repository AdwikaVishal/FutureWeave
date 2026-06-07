import React, { useState } from 'react';
import { SimulationProvider, useSim } from './context/SimulationContext';

import ContextForm from './ContextForm';
import TimelineView from './TimelineView';
import Dashboard from './components/Dashboard';
import MonteCarloAnalysis from './components/MonteCarloAnalysis';
import FutureChat from './components/FutureChat';
import AgentsView from './components/AgentsView';
import ConfidenceView from './components/ConfidenceView';
import CompareTwoModal from './CompareTwoModal';
import CounsellorDashboard from './CounsellorDashboard';
import OutcomeLibrary from './OutcomeLibrary';

const EXAMPLE_DECISIONS = [
  'CSE or AIML at VIT in 2026?',
  'Should I quit my job to start a company?',
  'MBA now or work for 2 more years first?',
  'Move to Bangalore for a startup or stay in a stable MNC?',
];

const TABS = [
  { id: 'simulation', label: 'Simulation' },
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'timeline', label: 'Timeline' },
  { id: 'agents', label: 'Agents' },
  { id: 'confidence', label: 'Confidence' },
  { id: 'montecarlo', label: 'Monte Carlo' },
  { id: 'chat', label: 'Future Chat' },
];

function AppContent() {
  const { result, loading, error, decision, context, runSimulation, reset, setError } = useSim();
  const [activeTab, setActiveTab] = useState('simulation');
  const [localDecision, setLocalDecision] = useState(decision);
  const [showCompare, setShowCompare] = useState(false);
  const [showCounsellor, setShowCounsellor] = useState(false);
  const [showOutcomes, setShowOutcomes] = useState(false);

  const handleSimulate = (ctx) => {
    if (!localDecision.trim()) {
      setError('Enter a decision first.');
      return;
    }
    runSimulation(localDecision, ctx);
    setActiveTab('simulation');
  };

  const handleReset = () => {
    reset();
    setLocalDecision('');
    setActiveTab('simulation');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const hasResult = !!result;

  return (
    <div className="app">
      <header>
        <h1>⟁ FutureWeave</h1>
        <p>Map your possible futures before you choose</p>
        {hasResult && (
          <div className="header-actions">
            <button type="button" className="header-action-btn" onClick={() => setShowCompare(true)}>
              ⇄ Compare Two Decisions
            </button>
            <button type="button" className="header-action-btn" onClick={() => setShowCounsellor(true)}>
              🎓 Counsellor Login
            </button>
            <button type="button" className="header-action-btn" onClick={() => setShowOutcomes(true)}>
              📚 Outcome Library
            </button>
          </div>
        )}
      </header>

      <main>
        {!hasResult && !loading && (
          <div className="input-area">
            <div className="decision-step">
              <div className="step-label">
                <span className="step-num">1</span>
                What decision are you facing?
              </div>
              <input
                type="text"
                className="decision-input"
                placeholder='e.g. "Should I quit my job to start a company?"'
                value={localDecision}
                onChange={(e) => setLocalDecision(e.target.value)}
              />
              <div className="decision-chips">
                <span className="chips-label">Try an example:</span>
                {EXAMPLE_DECISIONS.map((ex) => (
                  <button key={ex} type="button" className="decision-chip" onClick={() => setLocalDecision(ex)}>
                    {ex}
                  </button>
                ))}
              </div>
            </div>
            <div className="step-label" style={{ marginBottom: '0.75rem' }}>
              <span className="step-num">2</span>
              Tell us about yourself
            </div>
            <ContextForm onSubmit={handleSimulate} />
            {error && <div className="error">⚠ {error}</div>}
          </div>
        )}

        {loading && (
          <div className="loading-screen">
            <div className="loading-orb" />
            <div className="loader">◈ SIMULATING YOUR FUTURES...</div>
            <p className="loading-sub">
              Grounding in real salary data · Modeling causal outcomes · Writing your futures
            </p>
          </div>
        )}

        {hasResult && (
          <>
            <div className="results-header">
              <div className="results-decision-tag">
                <span className="results-decision-label">Your decision:</span>
                <span className="results-decision-text">{decision}</span>
              </div>
              <button type="button" className="new-sim-btn" onClick={handleReset}>
                ← New Simulation
              </button>
            </div>

            <div className="tabs">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
                  onClick={() => setActiveTab(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="tab-content">
              {activeTab === 'simulation' && <TimelineView data={result} decision={decision} />}
              {activeTab === 'dashboard' && <Dashboard data={result} decision={decision} />}
              {activeTab === 'timeline' && <TimelineView data={result} decision={decision} />}
              {activeTab === 'agents' && <AgentsView agents={result?.agents} />}
              {activeTab === 'confidence' && <ConfidenceView simulationResult={result} />}
              {activeTab === 'montecarlo' && <MonteCarloAnalysis decision={decision} context={context} />}
              {activeTab === 'chat' && <FutureChat simulationResult={result} decision={decision} />}
            </div>
          </>
        )}
      </main>

      {showCompare && (
        <CompareTwoModal context={context} onClose={() => setShowCompare(false)} />
      )}
      {showCounsellor && (
        <CounsellorDashboard onClose={() => setShowCounsellor(false)} />
      )}
      {showOutcomes && (
        <OutcomeLibrary onClose={() => setShowOutcomes(false)} />
      )}
    </div>
  );
}

export default function App() {
  return (
    <SimulationProvider>
      <AppContent />
    </SimulationProvider>
  );
}
