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
};

export type AppTheme = { dark: boolean; colors: ThemeColors };

const light: ThemeColors = {
  background:    '#f2f2f7',
  surface:       '#ffffff',
  surfaceVariant:'#f2f2f7',
  border:        '#e5e5ea',
  borderLight:   '#f2f2f7',
  text:          '#000000',
  textSecondary: '#3c3c43',
  textMuted:     '#8e8e93',
  textFaint:     '#c7c7cc',
  accent:        '#007aff',
  accentText:    '#ffffff',
  headerBg:      '#007aff',
  drawerBg:      '#ffffff',
  inputBg:       '#f2f2f7',
  cancelBg:      '#e5e5ea',
  cancelText:    '#3c3c43',
  userBubble:    '#007aff',
  aiBubble:      '#e5e5ea',
  aiBubbleText:  '#000000',
  placeholder:   '#c7c7cc',
  drawerActiveBg:'rgba(0,122,255,0.1)',
};

const dark: ThemeColors = {
  background:    '#000000',
  surface:       '#1c1c1e',
  surfaceVariant:'#2c2c2e',
  border:        '#38383a',
  borderLight:   '#2c2c2e',
  text:          '#ffffff',
  textSecondary: '#ebebf5',
  textMuted:     '#8e8e93',
  textFaint:     '#48484a',
  accent:        '#0a84ff',
  accentText:    '#ffffff',
  headerBg:      '#1c1c1e',
  drawerBg:      '#1c1c1e',
  inputBg:       '#2c2c2e',
  cancelBg:      '#3a3a3c',
  cancelText:    '#ebebf5',
  userBubble:    '#0a84ff',
  aiBubble:      '#2c2c2e',
  aiBubbleText:  '#ffffff',
  placeholder:   '#636366',
  drawerActiveBg:'rgba(10,132,255,0.18)',
};

type Ctx = { theme: AppTheme; isDark: boolean; toggleTheme: () => void };

const ThemeContext = createContext<Ctx>({
  theme: { dark: false, colors: light },
  isDark: false,
  toggleTheme: () => {},
});

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [isDark, setIsDark] = useState(false);
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
