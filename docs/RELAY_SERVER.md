# 公网中继/信令服务器配置

当前服务器提供两个能力：

- **信令**: 保存发送方的直连配对信息，让接收方用短密钥查询。
- **中继兜底**: 发送方同时上传 zip 存档包。接收方直连失败时，会从服务器下载。

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
uv run python src\relay_server.py --host 0.0.0.0 --port 8765 --storage ./relay_storage --ttl-seconds 86400
```

需要开放防火墙端口：

```text
TCP 8765
```

客户端 GUI 的“公网服务器”填写：

```text
http://你的服务器IP:8765
```

## 推荐生产方式

更推荐放到 Nginx/Caddy 后面，用 HTTPS：

```text
https://relay.example.com
```

反向代理需要转发：

```text
POST /api/sessions
GET  /api/sessions/<code>
PUT  /api/sessions/<code>/archive
GET  /api/sessions/<code>/archive
```

还需要提高请求体大小限制，因为存档 zip 可能较大。例如 Nginx：

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

过期清理会在创建/读取会话时触发。当前还没有后台定时清理线程。

## 当前限制

- 没有用户账号。
- 没有速率限制。
- 没有服务端鉴权。
- 中继文件还没有端到端加密。
- 适合 MVP 测试，不建议直接暴露为大规模公开服务。

## 当前客户端行为

如果 GUI 里填写了“公网服务器”：

1. 发送端生成直连配对信息。
2. 发送端把配对信息登记到服务器。
3. 发送端上传 zip 存档包作为中继兜底。
4. 接收端输入 `GST-...` 密钥。
5. 客户端先尝试直连。
6. 直连失败时自动从服务器下载 zip。
7. 下载完成后自动安装到本机对应存档目录。
