import { createSystem, defaultConfig, defineConfig } from "@chakra-ui/react";

const config = defineConfig({
  ...defaultConfig,
  globalCss: {
    "html, body": {
      bg: "bg",
      color: "fg",
    },
    "code, pre": {
      fontFamily: "mono",
    },
  },
  theme: {
    ...defaultConfig.theme,
    tokens: {
      ...defaultConfig.theme?.tokens,
      fonts: {
        ...defaultConfig.theme?.tokens?.fonts,
        body: { value: "Inter, system-ui, -apple-system, sans-serif" },
        heading: { value: "Inter, system-ui, -apple-system, sans-serif" },
        mono: { value: "'JetBrains Mono', 'Fira Code', monospace" },
      },
    },
  },
});

export const system = createSystem(config);
