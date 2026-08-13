import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactCompiler: true,
  output: "standalone",  // required for Docker multi-stage build
};

export default nextConfig;
