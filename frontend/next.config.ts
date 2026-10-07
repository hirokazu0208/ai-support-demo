import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Docker イメージ用に、実行に必要なファイルだけを .next/standalone に出力する
  // （frontend/Dockerfile が server.js で起動する。npm start の動作は変わらない）
  output: "standalone",
};

export default nextConfig;
