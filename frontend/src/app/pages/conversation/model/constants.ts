export const GUIDE_PANEL_WIDTH_LS = 'convGuidePanelWidthPx';
export const GUIDE_PANEL_MIN_W = 280;
export const GUIDE_PANEL_MAX_W = 560;
export const GUIDE_PANEL_DEFAULT_W = 320;

export const TTS_RATE_OPTIONS = ['-30%', '-20%', '-10%', '+0%', '+10%', '+20%', '+30%'];
const IELTS_BANDS: ReadonlyArray<string> = [
  '4',
  '4.5',
  '5',
  '5.5',
  '6',
  '6.5',
  '7',
  '7.5',
  '8',
  '8.5',
  '9',
];
export const LEVEL_OPTIONS = [
  { value: '', label: 'General' },
  ...IELTS_BANDS.map((b) => ({
    value: b,
    label: `Band ${b}`,
  })),
];

export const NOOP = { next: () => {}, error: () => {} };
