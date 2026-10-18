import eslintReact from 'eslint-plugin-react'
import eslintHooks from 'eslint-plugin-react-hooks'
import eslintA11y from 'eslint-plugin-jsx-a11y'
import eslintUnusedImports from 'eslint-plugin-unused-imports'

export default [
  { ignores: ['dist/**', 'node_modules/**', 'coverage/**'] },
  {
    files: ['src/**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 2024,
      sourceType: 'module',
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: {
        window: 'readonly', document: 'readonly', navigator: 'readonly',
        localStorage: 'readonly', sessionStorage: 'readonly',
        fetch: 'readonly', setTimeout: 'readonly', clearTimeout: 'readonly',
        URL: 'readonly', Blob: 'readonly', FormData: 'readonly',
      },
    },
    plugins: { react: eslintReact, 'react-hooks': eslintHooks, 'jsx-a11y': eslintA11y, 'unused-imports': eslintUnusedImports },
    settings: { react: { version: 'detect' } },
    rules: {
      'react-hooks/rules-of-hooks': 'error',
      'react/jsx-uses-vars': 'error',
      ...eslintA11y.flatConfigs.recommended.rules,
      // Downgraded to warn: real issues, but the tree predates the rule.
      // Ratchet to error once the backlog below is cleared.
      'jsx-a11y/click-events-have-key-events': 'warn',
      'jsx-a11y/no-static-element-interactions': 'warn',
      'jsx-a11y/no-noninteractive-element-interactions': 'warn',
      'jsx-a11y/media-has-caption': 'warn',
      'jsx-a11y/label-has-associated-control': 'warn',
      'jsx-a11y/no-autofocus': 'warn',
      'jsx-a11y/no-noninteractive-tabindex': 'warn',
      'react/jsx-uses-react': 'off',
      'react/react-in-jsx-scope': 'off',
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^React$' }],
      'unused-imports/no-unused-imports': 'warn',
      'no-empty': ['warn', { allowEmptyCatch: true }],
    },
  },
  {
    files: ['src/test/**', 'src/**/*.test.{js,jsx}'],
    rules: { 'no-unused-vars': 'off' },
  },
]
