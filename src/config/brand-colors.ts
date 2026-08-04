export const brandColors = {
  navy: {
    name: 'Navy',
    hex: '#262E84',
    hsl: '234 54% 33%',
  },
  teal: {
    name: 'Teal',
    hex: '#00A9A5',
    hsl: '178 100% 33%',
  },
  orange: {
    name: 'Orange',
    hex: '#FF9F5A',
    hsl: '30 85% 55%',
  },
  skyBlue: {
    name: 'Sky blue',
    hex: '#50B0F0',
    hsl: '201 70% 55%',
  },
} as const;

export type BrandColor = keyof typeof brandColors;
