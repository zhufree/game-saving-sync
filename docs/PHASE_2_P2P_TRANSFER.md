# 阶段二：P2P 配对与传输

**目标**: 替代旧 Syncthing 同步方案，实现两个用户之间的一次性点对点存档传输。
**优先级**: P0
**前置依赖**: 阶段一配置迁移、Steam 游戏库扫描、存档发现基础能力。

## 设计变化

旧方向是“持续同步文件夹”，新方向是“临时传输会话”。因此本阶段不再要求用户安装 Syncthing，也不再维护同步组。核心对象变为：

- 传输会话 `TransferSession`
- 配对密钥 `PairingKey`
- 对端信息 `PeerInfo`
- 存档包 `SavePackage`
- 传输结果 `TransferResult`

## 任务清单

### 2.1 配对密钥

- [x] 设计密钥格式。
- [x] 支持生成一次性密钥。
- [x] 支持解析和校验密钥。
- [x] 支持过期时间。
- [ ] 支持复制文本和二维码展示。

建议密钥内容：

```json
{
  "version": 1,
  "session_id": "uuid",
  "role": "sender",
  "public_key": "...",
  "candidates": [],
  "expires_at": "2026-04-22T12:00:00+08:00"
}
```

### 2.2 会话状态机

- [ ] `created`: 发送方已创建会话。
- [ ] `pairing`: 等待接收方连接。
- [ ] `connected`: 已建立连接。
- [ ] `transferring`: 正在传输。
- [ ] `verifying`: 正在校验。
- [ ] `completed`: 传输完成。
- [ ] `failed`: 传输失败。
- [ ] `expired`: 密钥过期。

### 2.3 存档包

- [x] 打包发送方选择的存档目录。
- [x] 生成文件清单。
- [x] 计算整体哈希。
- [ ] 写入游戏 appid、游戏名、存档规则 ID、相对目标路径。
- [x] 支持分块传输。

### 2.4 传输层抽象

先定义接口，再选择底层实现：

```python
class P2PTransport:
    def create_session(self) -> str: ...
    def join_session(self, pairing_key: str) -> None: ...
    def send_package(self, package_path: str) -> None: ...
    def receive_package(self, output_dir: str) -> str: ...
    def close(self) -> None: ...
```

当前实现：

- 已实现局域网/localhost TCP 一次性直连原型，配对密钥包含 host、port、session_id、token 和过期时间。
- 已实现 zip 存档包、manifest、sha256 校验、发送端监听、接收端下载到 incoming/。
- 尚未实现公网 NAT 穿透、信令服务或中继。

候选后续实现：

- WebRTC DataChannel: 公网 P2P 体验最好，但需要信令和打包验证。
- libp2p: 概念完整，但 Python 生态成熟度需要评估。
- 局域网 TCP + 手动连接: 适合作为最小原型，不足是公网能力弱。
- 临时中继: 可作为兜底方案，但会改变“纯 P2P”产品叙事。

### 2.5 校验和安全

- [ ] 传输前展示文件数量和总大小。
- [x] 传输后校验哈希。
- [ ] 接收方写入前必须完成安全快照。
- [ ] 检测目标游戏进程是否运行。
- [ ] 失败时保留临时文件并给出清理提示。

### 2.6 测试

- [ ] 配对密钥生成/解析测试。
- [ ] 会话状态机测试。
- [ ] 存档包文件清单和哈希测试。
- [ ] 本地回环传输测试。
- [ ] 断线/过期/校验失败测试。

## 验收标准

- [ ] 发送方可以生成一次性密钥。
- [ ] 接收方可以输入密钥并建立会话。
- [ ] 可以传输一个测试存档目录。
- [ ] 接收端可以校验文件完整性。
- [ ] 失败场景有清晰错误信息。

## 风险

1. NAT 穿透复杂度高，需要尽早做 spike。
2. 如果选择 WebRTC，可能需要轻量信令服务；这会影响“纯 P2P”定义。
3. 大存档传输需要进度、暂停/失败恢复策略。
4. 配对密钥不能长期有效，避免被误用。

