# 前端镜像：node 构建阶段 -> nginx 静态服务阶段
FROM node:20-alpine AS build
WORKDIR /app

# 先装依赖（利用层缓存）
COPY frontend/package*.json ./
RUN npm install

# 再拷贝源码并构建
COPY frontend/ ./
RUN npm run build

# 静态服务阶段
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
# 使用默认 nginx 配置即可静态托管 /usr/share/nginx/html（SPA 入口 index.html 在 / 可访问）
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
