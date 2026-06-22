export const RISK_THRESHOLDS = {
  CRITICAL: 80,
  HIGH: 61,
  MEDIUM: 31,
};

export const ZONE_COLORS = {
  green: { bg: '#EAF3DE', border: '#97C459', text: '#3B6D11', score: '#27500A', label: '#639922' },
  yellow: { bg: '#FAEEDA', border: '#EF9F27', text: '#854F0B', score: '#633806', label: '#BA7517' },
  red: { bg: '#FCEBEB', border: '#E24B4A', text: '#A32D2D', score: '#791F1F', label: '#E24B4A' },
};

export const CHANNEL_ICONS = {
  'SafetyIQ In-App': '\uD83D\uDCE3',
  'SMS': '\uD83D\uDCF1',
  'Webhook': '\U0001F514',
  'Slack Webhook': '\uD83D\uDCAC',
};

export const CHANNEL_NAMES = {
  'SafetyIQ In-App': 'Safety Officer',
  'SMS': 'Shift Supervisor (SMS)',
  'Webhook': 'Emergency Response Team (webhook)',
  'Slack Webhook': '#safety-alerts (Slack)',
};

export const DEFAULT_ZONES = [
  { id: 'Z1', name: 'Blast Furnace A', workers: 4, baseGas: 28, gasThresh: 50, permit: null, maintenance: null, changeover: false },
  { id: 'Z2', name: 'Coke Oven Bay', workers: 2, baseGas: 18, gasThresh: 45, permit: 'welding', maintenance: null, changeover: false },
  { id: 'Z3', name: 'Gas Processing', workers: 5, baseGas: 35, gasThresh: 50, permit: null, maintenance: null, changeover: false },
  { id: 'Z4', name: 'Ore Handling', workers: 3, baseGas: 12, gasThresh: 60, permit: 'hot_work', maintenance: null, changeover: false },
  { id: 'Z5', name: 'Slag Yard', workers: 2, baseGas: 8, gasThresh: 60, permit: null, maintenance: null, changeover: false },
  { id: 'Z6', name: 'Steam Plant', workers: 4, baseGas: 22, gasThresh: 50, permit: null, maintenance: null, changeover: true },
  { id: 'Z7', name: 'Cooling Tower', workers: 2, baseGas: 5, gasThresh: 45, permit: null, maintenance: null, changeover: false },
  { id: 'Z8', name: 'Control Room', workers: 2, baseGas: 2, gasThresh: 30, permit: null, maintenance: null, changeover: false },
];
