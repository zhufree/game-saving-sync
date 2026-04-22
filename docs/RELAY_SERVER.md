# 公网中继 / 信令服务器配置

当前服务器提供三个能力：

- **信令**: 保存发送方的直连配对信息，让接收方通过短密钥查询。
- **中继兜底**: 发送方同时上传 zip 存档包。接收方直连失败时，会从服务器下载。
- **版本检查**: 客户端可以查询当前是否需要更新，并获得 GitHub 项目地址。

注意：当前版本的中继文件还没有端到端加密，服务器管理员理论上可以读取 zip 内容。后续应加入客户端加密。

## 本地测试

```bash
uv run python src\relay_server.py --host 127.0.0.1 --port 8765 --storage ./relay_storage
```

客户端 GUI 的“公网服务器”填写：

```text
http://127.0.0.1:8765
```

这只适合本机测试。

## 云服务器运行

在一台有公网 IP 的服务器上：

```bash
uv sync --group dev
uv run python src\relay_server.py --host 0.0.0.0 --port 8765 --storage ./relay_storage --ttl-seconds 86400 --latest-version 0.2.0
```

需要开放防火墙端口：

```text
TCP 8765
```

客户端 GUI 的“公网服务器”填写：

```text
http://你的服务器IP:8765
```

## 版本检查 API

请求：

```text
GET /api/version?current_version=0.2.0
```

返回示例：

```json
{
  "app_name": "Game Save Transfer",
  "current_version": "0.2.0",
  "latest_version": "0.3.0",
  "update_available": true,
  "update_url": "https://github.com/zhufree/game-saving-sync",
  "github_url": "https://github.com/zhufree/game-saving-sync"
}
```

服务端参数：

```bash
--latest-version 0.3.0
--update-url https://github.com/zhufree/game-saving-sync
```

如果 `current_version` 小于 `latest_version`，`update_available` 会是 `true`，同时 `update_url` 会返回 GitHub 地址。

## API 路径

```text
POST /api/sessions
GET  /api/sessions/<code>
PUT  /api/sessions/<code>/archive
GET  /api/sessions/<code>/archive
GET  /api/version?current_version=<version>
```

## 推荐生产方式

更推荐放到 Nginx/Caddy 后面，并使用 HTTPS：

```text
https://relay.example.com
```

Nginx 示例：

```nginx
server {
    listen 443 ssl;
    server_name relay.example.com;

    client_max_body_size 2g;

    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 数据和清理

服务器会在 `--storage` 指定目录保存：

```text
<code>.json
<code>.zip
```

`--ttl-seconds` 控制会话过期时间，默认 86400 秒，也就是 24 小时。

## 当前限制

- 没有用户账号。
- 没有速率限制。
- 没有服务端鉴权。
- 中继文件还没有端到端加密。
- 适合 MVP 测试，不建议直接暴露为大规模公开服务。
