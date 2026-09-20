import * as React from 'react'

const ThemeProviderContext = React.createContext(null)

export function ThemeProvider({ children, defaultTheme = 'system', storageKey = 'voice-ai-theme', ...props }) {
  const [theme, setThemeState] = React.useState(() => localStorage.getItem(storageKey) || defaultTheme)

  React.useEffect(() => {
    const root = window.document.documentElement
    root.classList.remove('light', 'dark')

    if (theme === 'system') {
      const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
      root.classList.add(systemTheme)
      return
    }

    root.classList.add(theme)
  }, [theme])

  const setTheme = React.useCallback(
    (value) => {
      localStorage.setItem(storageKey, value)
      setThemeState(value)
    },
    [storageKey],
  )

  const value = React.useMemo(() => ({ theme, setTheme }), [theme, setTheme])

  return (
    <ThemeProviderContext.Provider {...props} value={value}>
      {children}
    </ThemeProviderContext.Provider>
  )
}

export function useTheme() {
  const context = React.useContext(ThemeProviderContext)
  if (!context) throw new Error('useTheme must be used within a ThemeProvider')
  return context
}
