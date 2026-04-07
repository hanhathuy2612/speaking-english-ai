import { IELTS_SPEAKING_BAND_VALUES } from '../../../shared/ielts-levels';

export const GUIDE_PANEL_WIDTH_LS = 'convGuidePanelWidthPx';
export const GUIDE_PANEL_MIN_W = 280;
export const GUIDE_PANEL_MAX_W = 560;
export const GUIDE_PANEL_DEFAULT_W = 320;

export const TTS_RATE_OPTIONS = ['-30%', '-20%', '-10%', '+0%', '+10%', '+20%', '+30%'];
export const LEVEL_OPTIONS = [
  { value: '', label: 'General' },
  ...IELTS_SPEAKING_BAND_VALUES.map((b) => ({
    value: b,
    label: `Band ${b}`,
  })),
];

export const NOOP = { next: () => {}, error: () => {} };
