import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  webpack: (config, { dir }) => {
    // dir is the directory where next.config.ts is located (Frontend/)
    const frontendRoot = path.resolve(dir);
    
    // Configure alias for @ to point to the Frontend root
    // Ensure resolve and alias objects exist
    config.resolve = config.resolve || {};
    config.resolve.alias = config.resolve.alias || {};
    
    // Set the @ alias to the frontend root directory
    // This ensures @/lib/api resolves to Frontend/lib/api
    config.resolve.alias['@'] = frontendRoot;
    
    // Also ensure extensions are configured
    config.resolve.extensions = config.resolve.extensions || [];
    if (!config.resolve.extensions.includes('.ts')) {
      config.resolve.extensions.push('.ts', '.tsx', '.js', '.jsx');
    }
    
    return config;
  },
};

export default nextConfig;
