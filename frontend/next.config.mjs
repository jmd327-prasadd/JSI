import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Pins the workspace root to this folder -- avoids Next.js inferring it from
  // an unrelated package-lock.json higher up the filesystem (e.g. a stray one
  // in the user's home directory from some other project).
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
