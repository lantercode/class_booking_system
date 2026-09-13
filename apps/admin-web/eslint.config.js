/* jshint esversion: 6, module: true */
import pluginVue from 'eslint-plugin-vue'
import vueTsEslintConfig from '@vue/eslint-config-typescript'
import eslintPluginPrettier from 'eslint-plugin-prettier'

export default [
  {
    name: 'app/files-to-lint',
    files: ['**/*.{ts,mts,tsx,vue}'],
  },
  {
    name: 'app/files-to-ignore',
    ignores: ['**/dist/**', '**/node_modules/**'],
  },
  ...pluginVue.configs['flat/recommended'],
  ...vueTsEslintConfig(),
  {
    rules: {
      // 关闭 Vue 组件命名规则
      'vue/multi-word-component-names': 'off',

      // 关闭与 Prettier 冲突的 Vue 模板格式化规则
      'vue/max-attributes-per-line': 'off',
      'vue/singleline-html-element-content-newline': 'off',
      'vue/html-indent': 'off',
      'vue/attribute-hyphenation': 'off',
      'vue/first-attribute-linebreak': 'off',
      'vue/no-v-html': 'off',
      'vue/html-closing-bracket-newline': 'off', // 关闭闭合标签换行规则
      'vue/multiline-html-element-content-newline': 'off', // 关闭多行内容换行规则
      'vue/html-closing-bracket-spacing': 'off', // 关闭闭合括号前空格规则
      'vue/html-self-closing': 'off', // 允许自闭合标签

      // TypeScript 规则调整
      '@typescript-eslint/no-explicit-any': 'off', // 允许使用 any
      '@typescript-eslint/no-unused-vars': 'off', // 允许未使用的变量
      '@typescript-eslint/no-empty-object-type': 'off', // 允许 {} 类型（Vue 组件声明需要）
      'vue/no-unused-vars': 'off', // 允许 Vue 中未使用的变量
    },
  },
  {
    plugins: {
      prettier: eslintPluginPrettier,
    },
    rules: {
      'prettier/prettier': 'error',
    },
  },
]
