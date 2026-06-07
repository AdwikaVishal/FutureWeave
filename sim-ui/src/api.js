import axios from 'axios';

const API = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000',
  timeout: 120000,
});

API.interceptors.response.use(
  (res) => res,
  (err) => {
    const detail = err.response?.data?.detail || err.message || 'Request failed';
    return Promise.reject(new Error(detail));
  },
);

export async function simulate(decision, context, user_email) {
  const { data } = await API.post('/simulate', { decision, context, user_email });
  return data;
}

export async function getSimulation(id) {
  const { data } = await API.get(`/simulation/${id}`);
  return data;
}

export async function followUp(simulation_id, actual_timeline) {
  const { data } = await API.post('/followup', null, { params: { simulation_id, actual_timeline } });
  return data;
}

export async function pivot(original_timeline, event_year, alternative_outcome, decision, context) {
  const { data } = await API.post('/pivot', {
    original_timeline, event_year, alternative_outcome, decision, context,
  });
  return data;
}

export async function score(simulation_id, weights) {
  const { data } = await API.post('/score', { simulation_id, weights });
  return data;
}

export async function peerComparison(decisionKeywords) {
  const { data } = await API.get('/peer-comparison', { params: { decision_keywords: decisionKeywords } });
  return data;
}

export async function compareTwo(decision_a, decision_b, context, user_email) {
  const { data } = await API.post('/compare-two', { decision_a, decision_b, context, user_email });
  return data;
}

export async function counsellorStudents(counsellor_email) {
  const { data } = await API.get('/counsellor/students', { params: { counsellor_email } });
  return data;
}

export async function counsellorNote(simulation_id, counsellor_email, note) {
  const { data } = await API.post('/counsellor/note', { simulation_id, counsellor_email, note });
  return data;
}

export async function jobMarket(role, location, skills) {
  const { data } = await API.get('/job-market', { params: { role, location, skills } });
  return data;
}

export async function economicResearch(decision, context, country) {
  const { data } = await API.post('/economic-research', { decision, context, country });
  return data;
}

export async function outcomes(limit) {
  const { data } = await API.get('/outcomes', { params: { limit: limit || 20 } });
  return data;
}

export async function simulateCompare(decision, context, user_email) {
  const { data } = await API.post('/simulate-compare', { decision, context, user_email });
  return data;
}

export async function simulateV2(decision, context, enable_monte_carlo, monte_carlo_iterations) {
  const { data } = await API.post('/simulate-v2', {
    decision, context, enable_monte_carlo, monte_carlo_iterations,
  });
  return data;
}

export async function futureChat(timeline_label, question, future_self_persona, timeline_data, conversation_history) {
  const { data } = await API.post('/future-chat', {
    timeline_label, question, future_self_persona, timeline_data, conversation_history,
  });
  return data;
}

export async function monteCarlo(decision, context, iterations) {
  const { data } = await API.post('/monte-carlo', { decision, context, iterations: iterations || 100 });
  return data;
}

export async function memoryQuery(query, n_results, filter_type) {
  const { data } = await API.post('/memory/query', { query, n_results: n_results || 5, filter_type });
  return data;
}

export async function memoryStore(user_id, decision, simulation_id, result) {
  const params = { user_id, decision, simulation_id };
  const { data } = await API.post('/memory/store', null, { params, data: { result } });
  return data;
}

export default API;
