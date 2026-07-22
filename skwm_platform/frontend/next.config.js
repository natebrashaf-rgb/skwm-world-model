/**
 * 把以下 rewrites 合并到你现有的 next.config.js（项目根目录）。
 * 作用：前端 fetch("/api/xxx") 会被代理到 Python 后端 localhost:8000，
 * 避免跨域问题，也不用改各页面里的请求地址。
 */
/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

module.exports = nextConfig;
