# Two stages: build the bundle with node, serve it with nginx (D5).
#
# The runtime image contains no node and no source - only static files and nginx - so
# the thing that ships is exactly the thing `npm run build` produced.

FROM node:22-alpine AS build

WORKDIR /app

# Dependencies first so a source change does not reinstall node_modules.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.29-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
