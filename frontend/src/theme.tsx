import { createContext, useCallback, useContext, useState, type ReactNode } from 'react';

export type ThemeColors = {
  background: string;
  surface: string;
  surfaceVariant: string;
  border: string;
  borderLight: string;
  text: string;
  textSecondary: string;
  textMuted: string;
  textFaint: string;
  accent: string;
  accentText: string;
  headerBg: string;
  drawerBg: string;
  inputBg: string;
  cancelBg: string;
  cancelText: string;
  userBubble: string;
  aiBubble: string;
  aiBubbleText: string;
  placeholder: string;
  drawerActiveBg: string;
  success: string;
  danger: string;
};

export type AppTheme = { dark: boolean; colors: ThemeColors };

const light: ThemeColors = {
  background:    '#f0eeff',
  surface:       '#ffffff',
  surfaceVariant:'#e8e4ff',
  border:        '#d4ccf7',
  borderLight:   '#e8e4ff',
  text:          '#1a1040',
  textSecondary: '#3d2e7c',
  textMuted:     '#7a6aa0',
  textFaint:     '#c0b3e8',
  accent:        '#6c5ce7',
  accentText:    '#ffffff',
  headerBg:      '#6c5ce7',
  drawerBg:      '#ffffff',
  inputBg:       '#ece9ff',
  cancelBg:      '#e2deff',
  cancelText:    '#3d2e7c',
  userBubble:    '#6c5ce7',
  aiBubble:      '#f0eeff',
  aiBubbleText:  '#1a1040',
  placeholder:   '#c0b3e8',
  drawerActiveBg:'rgba(108,92,231,0.1)',
  success:       '#22c55e',
  danger:        '#ef4444',
};

const dark: ThemeColors = {
  background:    '#0d0d14',
  surface:       '#151520',
  surfaceVariant:'#1d1d2c',
  border:        '#2a2a3d',
  borderLight:   '#1d1d2c',
  text:          '#e8e8f5',
  textSecondary: '#b0b0cc',
  textMuted:     '#6a6a8a',
  textFaint:     '#3a3a52',
  accent:        '#7c6ef5',
  accentText:    '#ffffff',
  headerBg:      '#151520',
  drawerBg:      '#0d0d14',
  inputBg:       '#1d1d2c',
  cancelBg:      '#252536',
  cancelText:    '#b0b0cc',
  userBubble:    '#6558d3',
  aiBubble:      '#1d1d2c',
  aiBubbleText:  '#e8e8f5',
  placeholder:   '#4a4a65',
  drawerActiveBg:'rgba(124,110,245,0.15)',
  success:       '#4ade80',
  danger:        '#f87171',
};

type Ctx = { theme: AppTheme; isDark: boolean; toggleTheme: () => void };

const ThemeContext = createContext<Ctx>({
  theme: { dark: true, colors: dark },
  isDark: true,
  toggleTheme: () => {},
});

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [isDark, setIsDark] = useState(true);
  const toggleTheme = useCallback(() => setIsDark((d) => !d), []);
  const theme: AppTheme = isDark
    ? { dark: true, colors: dark }
    : { dark: false, colors: light };
  return (
    <ThemeContext.Provider value={{ theme, isDark, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export const useTheme = () => useContext(ThemeContext);
