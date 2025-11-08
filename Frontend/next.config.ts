import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  webpack: (config, { dir }) => {
    // dir is the directory where next.config.ts is located (Frontend/)
    const frontendRoot = path.resolve(dir);
    
    // Configure alias for @ to point to the Frontend root
    if (!config.resolve) {
      config.resolve = {};
    }
    
    if (!config.resolve.alias) {
      config.resolve.alias = {};
    }
    
    // Set the @ alias to the frontend root directory
    // This ensures @/lib/api resolves to Frontend/lib/api
    config.resolve.alias['@'] = frontendRoot;
    
    return config;
  },
};

export default nextConfig;
