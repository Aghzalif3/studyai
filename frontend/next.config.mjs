/** Interface exportée en fichiers statiques, servis par le moteur Python (une seule adresse). */
const isDev = process.env.NODE_ENV !== "production";
const backend = process.env.STUDYAI_BACKEND || "http://127.0.0.1:8765";

const config = {
  output: isDev ? undefined : "export",
  images: { unoptimized: true },
  trailingSlash: false,
  // En développement (npm run dev), les appels /api sont transmis au moteur Python.
  ...(isDev ? { rewrites: async () => [{ source: "/api/:path*", destination: `${backend}/api/:path*` }] } : {}),
};
export default config;
