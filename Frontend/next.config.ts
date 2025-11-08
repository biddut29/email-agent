import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  webpack: (config, { dir }) => {
    const projectRoot = path.resolve(dir);
    config.resolve.alias = {
      ...config.resolve.alias,
      '@': projectRoot,
    };
    return config;
  },
};

export default nextConfig;
