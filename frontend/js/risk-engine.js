export function computeScore(z, gasHistory) {
  let score = 0;
  const reasons = [];

  const currentGas = z.currentGas ?? z.baseGas ?? 0;
  const gasThresh = z.gasThresh ?? 50;
  const pct = gasThresh > 0 ? currentGas / gasThresh : 0;

  if (pct > 0.8) {
    score += 30;
    reasons.push({ w: '+30', t: 'Gas reading approaching threshold', pct: Math.round(pct * 100) });
  } else if (pct > 0.6) {
    score += 15;
    reasons.push({ w: '+15', t: 'Gas elevated (>60% of threshold)', pct: Math.round(pct * 100) });
  }

  const gasTrending = gasHistory && gasHistory.length > 2
    ? gasHistory[gasHistory.length - 1] > gasHistory[gasHistory.length - 3] + 3
    : false;

  if (z.permit === 'hot_work' && gasTrending) {
    score += 40;
    reasons.push({ w: '+40', t: 'Hot work permit active + rising gas trend', pct: null });
  } else if (z.permit === 'hot_work') {
    score += 15;
    reasons.push({ w: '+15', t: 'Hot work permit active in zone', pct: null });
  } else if (z.permit === 'welding') {
    score += 8;
    reasons.push({ w: '+8', t: 'Welding permit active', pct: null });
  }

  if (z.maintenance === 'confined_space_entry') {
    score += 20;
    reasons.push({ w: '+20', t: 'Confined space entry in progress', pct: null });
  }

  if (z.changeover) {
    score += 15;
    reasons.push({ w: '+15', t: 'Shift changeover — reduced supervision continuity', pct: null });
  }

  if ((z.workers ?? 0) > 4) {
    score += 5;
    reasons.push({ w: '+5', t: 'High worker density in zone', pct: null });
  }

  score = Math.min(score, 100);
  return { score, reasons };
}

export function computeSingleSensorScore(z) {
  const currentGas = z.currentGas ?? z.baseGas ?? 0;
  const gasThresh = z.gasThresh ?? 50;
  const pct = gasThresh > 0 ? currentGas / gasThresh : 0;

  let score = 0;
  const reasons = [];
  if (pct >= 1.0) {
    score = 100;
    reasons.push({ w: '+100', t: 'Gas threshold breached — standalone alarm', pct: Math.round(pct * 100) });
  } else if (pct > 0.8) {
    score = 60;
    reasons.push({ w: '+60', t: 'Gas near threshold (warning level)', pct: Math.round(pct * 100) });
  }
  return { score, reasons };
}

export function computeDetectionGap(compoundScore, singleScore) {
  return {
    compoundDetected: compoundScore >= 61,
    singleDetected: singleScore >= 61,
    compoundOnlyDetection: compoundScore >= 61 && singleScore < 61,
    compoundScore,
    singleScore,
    gapSize: compoundScore >= 61 && singleScore < 61 ? compoundScore - singleScore : 0,
  };
}

export function getRiskLabel(score) {
  if (score >= 80) return 'CRITICAL';
  if (score >= 61) return 'HIGH';
  if (score >= 31) return 'MEDIUM';
  return 'LOW';
}

export function getZoneClass(score) {
  return score >= 61 ? 'zone-red' : score >= 31 ? 'zone-yellow' : 'zone-green';
}

export function getScoreClass(score) {
  return score >= 61 ? 'score-red' : score >= 31 ? 'score-yellow' : 'score-green';
}

export function getBadgeClass(score) {
  return score >= 61 ? 'badge-red' : score >= 31 ? 'badge-yellow' : 'badge-green';
}

export function recalcLocalScores(state) {
  state.forEach(z => {
    const gh = z.gasHistory || [z.baseGas];
    const result = computeScore(z, gh);
    const singleResult = computeSingleSensorScore(z);
    z.score = result.score;
    z.reasons = result.reasons;
    z.singleScore = singleResult.score;
    z.detectionGap = computeDetectionGap(result.score, singleResult.score);
    z.gasTrending = gh.length > 2 ? gh[gh.length - 1] > gh[gh.length - 3] + 3 : false;
  });
}
