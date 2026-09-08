/** @type {import('ts-jest').JestConfigWithTsJest} */
export default {
  preset: 'ts-jest',
  testEnvironment: 'node',
  roots: ['<rootDir>/src'],
  testMatch: ['**/*.test.ts', '**/*.test.tsx'],
  // jsdom has no TextEncoder/TextDecoder; react-router-dom's data routers
  // need them at import time. See src/test_support/text_encoder_polyfill.ts.
  setupFiles: ['<rootDir>/src/test_support/text_encoder_polyfill.ts'],
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx'],
  // The built @eyra/feldspar cannot be resolved from jest (its exports map has
  // no "require" condition). Map the specifier onto a source re-export so tests
  // exercise the real feldspar code. See src/test_support/feldspar_test_shim.ts.
  moduleNameMapper: {
    '^@eyra/feldspar$': '<rootDir>/src/test_support/feldspar_test_shim.ts',
    // feldspar's button.tsx imports icon SVGs at module scope; jest has no
    // loader for raw SVG XML, so stub it (see src/test_support/svg_mock.js).
    '\\.svg$': '<rootDir>/src/test_support/svg_mock.js',
    // jest runs these modules as CommonJS and cannot parse `import.meta`, which
    // src/build_env.ts exists to contain. See src/test_support/build_env_mock.ts.
    '^.*/build_env$': '<rootDir>/src/test_support/build_env_mock.ts',
  },
  transform: {
    '^.+\\.tsx?$': ['ts-jest', {
      useESM: true,
      tsconfig: '<rootDir>/tsconfig.test.json',
    }],
  },
  extensionsToTreatAsEsm: ['.ts', '.tsx'],
};
