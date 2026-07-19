# 任务：将 zai-sidecar data URL 支持同步到 fire 源仓库并打通 web-network

**目标仓库**: `fire@192.168.172.4:/home/fire/api-mcp-hub`  
**状态**: starl-38 生产环境已验证，需回传源仓库并补齐网络配置  
**记录时间**: 2026-07-19

---

## 背景

DeerFlow 通过 hub relay 调用 `zai-mcp-server` 视觉工具时，因 `zai-sidecar` 容器无法访问 DeerFlow 沙箱本地图片路径而失败。已在 starl-38 生产环境做了以下修复：

1. zai-sidecar 构建期补丁：支持 `data:image/...` 和 `data:video/...` base64 URL。
2. supergateway body 限制提升到 25mb。
3. nginx-proxy `client_max_body_size 25m;`。
4. DeerFlow gateway 自动将 `/mnt/user-data/` 本地媒体路径转成 data URL 后调用远程 MCP 工具。

**剩余阻塞**: `zai-sidecar` 仍无法访问 `open.bigmodel.cn`，因为只挂在 `hub-internal`（`Internal: true`）网络。

---

## fire 源仓库需要完成的工作

### 1. 补齐 starl-38 已做但未回传的改动

以下改动当前只在 starl-38 `/home/starl/api-mcp-hub`，需要复制/同步到 fire 源仓库：

#### 1.1 `zai-sidecar/Dockerfile`

```dockerfile
FROM node:22-slim
WORKDIR /app
RUN npm install -g supergateway@3.4.3 @z_ai/mcp-server@0.1.4
COPY patches/ ./patches/
RUN node ./patches/apply-data-url-patch.mjs
COPY entrypoint.mjs ./entrypoint.mjs
CMD ["node", "/app/entrypoint.mjs"]
```

#### 1.2 `zai-sidecar/patches/apply-data-url-patch.mjs`

从 starl-38 复制：

```bash
scp starl-38:/home/starl/api-mcp-hub/zai-sidecar/patches/apply-data-url-patch.mjs \
  fire:/home/fire/api-mcp-hub/zai-sidecar/patches/apply-data-url-patch.mjs
```

#### 1.3 `zai-sidecar/patches/apply-data-url-patch.test.mjs`

从 starl-38 复制：

```bash
scp starl-38:/home/starl/api-mcp-hub/zai-sidecar/patches/apply-data-url-patch.test.mjs \
  fire:/home/fire/api-mcp-hub/zai-sidecar/patches/apply-data-url-patch.test.mjs
```

#### 1.4 `zai-sidecar/tests/run_containerized.sh`

从 starl-38 复制并设置可执行：

```bash
scp starl-38:/home/starl/api-mcp-hub/zai-sidecar/tests/run_containerized.sh \
  fire:/home/fire/api-mcp-hub/zai-sidecar/tests/run_containerized.sh
chmod +x /home/fire/api-mcp-hub/zai-sidecar/tests/run_containerized.sh
```

#### 1.5 `zai-sidecar/AGENTS.md` 测试说明

确保 Testing Requirements 部分包含：

```markdown
### Testing Requirements

- Run patch unit tests: `node --test patches/` (or `./tests/run_containerized.sh` for the verify_all runner contract).
- Verify via `GET http://zai-sidecar:58097/health` or the relay profile tool snapshot (`initialize`/`tools/list` through mcp-relay).
```

#### 1.6 `scripts/verify_all.sh`

在 `SUITES` 数组中 `egress-gateway` 条目下方新增：

```bash
  "zai-sidecar|bash $REPO_ROOT/zai-sidecar/tests/run_containerized.sh"
```

注意使用 `bash` 而非 `sh`，因为 runner 用了 `set -euo pipefail`。

#### 1.7 `infra/nginx/mcphub.server.starlove.top.conf`

在 443 server 块内（如 `ssl_protocols` 之后）添加：

```nginx
    client_max_body_size 25m;
```

---

### 2. 打通 zai-sidecar 出站网络（新增）

#### 2.1 修改 `docker-compose.yml`

将 `zai-sidecar` 服务改为同时挂载 `hub-internal` 和 `web-network`：

```yaml
  zai-sidecar:
    build:
      context: ./zai-sidecar
    env_file: ${HUB_ENV_FILE:-.env}
    environment:
      OPENBAO_ADDR: http://openbao:58200
      OPENBAO_TOKEN: ${ZAI_OPENBAO_TOKEN}
    depends_on: [openbao]
    expose: ["58097"]
    networks:
      - hub-internal
      - web-network
```

说明：
- `hub-internal` 保留，保证 `mcp-relay` 仍能通过内部网络访问 zai-sidecar。
- `web-network` 提供外部出站能力，使 `@z_ai/mcp-server` 能调用 `open.bigmodel.cn`。
- 参考：`legacy-compat-mcp`、`control-plane`、`patent-data-mcp` 已采用相同双网络模式。

#### 2.2 确认 networks 定义

`docker-compose.yml` 底部应已有：

```yaml
networks:
  hub-internal:
    internal: true
  web-network:
    external: true
```

若 `web-network` 未定义，需补上。

---

## 提交与同步流程

### fire 源仓库

```bash
cd /home/fire/api-mcp-hub
# 确认上述文件都已修改/新增
git add zai-sidecar/Dockerfile \
  zai-sidecar/patches/ \
  zai-sidecar/tests/ \
  zai-sidecar/AGENTS.md \
  infra/nginx/mcphub.server.starlove.top.conf \
  scripts/verify_all.sh \
  docker-compose.yml

git commit -m "feat(zai-sidecar): data URL support + outbound web-network

- Build-time patch for @z_ai/mcp-server@0.1.4 to accept data URLs.
- Raise supergateway JSON body limit to 25mb.
- Add nginx client_max_body_size 25m.
- Add patch unit tests and wire into verify_all.
- Attach zai-sidecar to web-network so it can reach open.bigmodel.cn.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"

git push <remote> <branch>
```

### starl-38 生产环境同步

```bash
ssh starl-38
cd /home/starl/api-mcp-hub
# 拉取 fire 源仓库的最新变更（根据实际 remote/branch 调整）
git pull <remote> <branch>

# 重建并重启 zai-sidecar
docker compose up -d --build zai-sidecar

# 验证容器在 web-network 上
docker network inspect web-network | grep zai-sidecar

# 验证 DNS 和外部连通性
docker exec api-mcp-hub-zai-sidecar-1 node -e "require('dns').lookup('open.bigmodel.cn', (e,a)=>console.log(e||a))"

# 验证补丁仍生效
docker exec api-mcp-hub-zai-sidecar-1 node -e "console.log(require('fs').readFileSync('/usr/local/lib/node_modules/@z_ai/mcp-server/build/core/file-service.js','utf8').includes('isDataUrl'))"
docker exec api-mcp-hub-zai-sidecar-1 node -e "console.log(require('fs').readFileSync('/usr/local/lib/node_modules/supergateway/dist/gateways/stdioToStatefulStreamableHttp.js','utf8').includes(\"limit: '25mb'\"))"

# 验证 nginx 配置并 reload
docker exec nginx-proxy nginx -t
docker exec nginx-proxy nginx -s reload

# 运行 verify_all
./scripts/verify_all.sh
```

---

## 端到端验证

1. 在 DeerFlow（starl-38）上传一张图片。
2. 提问让 agent 分析图片内容。
3. 观察 gateway 日志：
   - `zai-mcp-server_analyze_image` 应收到 `data:image/...;base64,...` 参数。
   - 不应再出现 `Image file not found`。
4. 预期结果：返回 GLM 视觉分析文本（会产生一次 GLM 视觉 API 调用费用）。

---

## 注意事项

- **版本 pin 不变**: 保持 `supergateway@3.4.3` 和 `@z_ai/mcp-server@0.1.4` 不变；所有改动通过构建期锚点补丁完成。
- **网络变更风险**: 加 `web-network` 后 zai-sidecar 具备外网访问能力，攻击面略有增加，但与 `legacy-compat-mcp` 等已有服务一致。
- **DeerFlow 客户端零改动**: 已通过 DeerFlow gateway 的 MCP 参数自动转换补丁实现。
- **不要提交 token**: `.env` 中的 `ZAI_OPENBAO_TOKEN`、`MCP_RELAY_AUTHORIZATION` 等保持不变，不要写入仓库。

---

## 参考提交

- starl-38 hub 已提交: `e0c6947`
- starl-38 DeerFlow 已 cherry-pick: `e526d20f`
- lxdd DeerFlow 源提交: `caedd2cd1`
