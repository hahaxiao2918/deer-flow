# 任务:zai 视觉工具支持 data URL(hub 侧 zai-sidecar 补丁)

**记录日期**:2026-07-19 · **状态**:已完成(hub 侧已在 starl-38 部署并提交,DeerFlow 客户端零改动)
**决策人**:用户本人 · **记录**:Claude(hub 侧)

## 背景与问题

Deerflow 里丢图片提问时,agent 调 `zai-mcp-server` 的 `analyze_image` /
`extract_text_from_screenshot` 报 "couldn't find the file",随后代码解释器
兜底执行一长串(ls / cp / base64 / PIL / pytesseract / easyocr)。

**根因(已在 38 容器内源码核实)**:

- zai 视觉工具实际运行在 **38 的 zai-sidecar 容器**(`@z_ai/mcp-server@0.1.4`
  + supergateway 3.4.3),Deerflow 沙箱路径(`/mnt/user-data/uploads/...`)
  只存在于 lxdd 本地,容器内 `fs.existsSync()` 找不到。
- stock 0.1.4 的 `isUrl()` **只认 `http:`/`https:` 协议**
  (`build/core/file-service.js`),`data:image/...;base64,...` 会落到
  本地文件分支再次报 not found —— 所以即使 agent 自发 base64 了也传不进去。
- 失败调用 ~10ms 内返回(在调 Z.AI API 之前拦截),**不产生费用**;
  relay 审计显示传输层全部 200,hub 无故障。

## 已拍板方案

给 zai-sidecar 打构建期补丁,接受 `data:image/...;base64,...` 作为合法
`image_source`(GLM 视觉 API 原生支持 base64 data URL)。
**Deerflow 客户端零改动**——agent 本来就会自发 base64 编码,
补丁生效后其自救路径直接可用。全程仍走 hub
(`mcphub.server.starlove.top/relay/zai-mcp-server/mcp`)。

## 实施清单(hub 仓库,fire: /home/fire/api-mcp-hub)

1. **zai-sidecar 补丁脚本** `zai-sidecar/patches/apply-data-url-patch.mjs`:
   对容器内 `@z_ai/mcp-server/build/core/file-service.js` 做锚点替换:
   - `validateImageSource()`:data URL 前缀校验(`data:image/(png|jpeg|jpg|webp|gif);base64,`)
     + 解码后尺寸 ≤ 5MB 守卫,合法则直接 return;
   - `encodeImageToBase64()`:已是 data URL 则原样返回。
   - 锚点找不到则**构建失败**(防上游包版本漂移静默失效)。
   Dockerfile:`COPY patches/ ./patches/` + npm install 后 `RUN node ./patches/apply-data-url-patch.mjs`。
2. **supergateway 请求体上限**:`dist/gateways/stdioToStatefulStreamableHttp.js:26`
   `app.use(express.json())` 默认 **100kb**,base64 图片必然超限 →
   同样构建期锚点补丁改为 `express.json({ limit: '25mb' })`。
3. **nginx 边缘 `client_max_body_size`**:38 上 443 由 **nginx-proxy 容器**
   承接(注意:hub compose 栈里没有 nginx;`~/api-mcp-hub/mcphub.server.starlove.top.conf`
   是旧拷贝,不是活配置——先 `docker ps` + 进 nginx-proxy 容器确认活的 conf),
   server 块加 `client_max_body_size 25m;`,改前备份,改后 `nginx -s reload`。
4. **mcp-relay 无需改**:流式转发,无请求体限制(已核实)。
5. **测试**:补丁脚本配套 `node --test` 小套件(data URL 接受 / 超限拒绝 /
   http URL 直通 / 缺文件报错);是否纳入 verify_all(现为 12 suites)届时定。
6. **部署**:只重建 zai-sidecar(不动其他服务);e2e:经 relay 用一张
   tiny base64 PNG 调 `analyze_image`,返回视觉文本即通过
   (会产生 1 次 GLM 视觉调用费,金额极小)。

## 完成记录

- **starl-38 部署**:2026-07-19 已完成。
  - zai-sidecar 重建、nginx reload、`verify_all` 13/13 OK。
  - DeerFlow gateway 已 cherry-pick 部署 MCP 参数自动转换补丁,将 `/mnt/user-data/` 下的本地图片/视频路径在调用远程(HTTP/SSE)MCP 工具前转成 data URL。
- **提交**:
  - hub 侧:starl-38 `/home/starl/api-mcp-hub` commit `e0c6947`。
  - DeerFlow 后端:lxdd `codex/shanghai-electric` commit `caedd2cd1`,并已 push 到 origin;starl-38 `codex/deerflow-patent-data-mcp` commit `e526d20f`(cherry-pick)。
- **验证**:
  - 单元测试 18 项全部通过;现有 MCP 测试 69 项全部通过。
  - data URL 已被 `analyze_image` 接受,不再报 `Image file not found`。
- **剩余阻塞(基础设施,非本补丁可解)**:
  - zai-sidecar 容器所在 `hub-internal` Docker 网络为 `Internal: true`,无法解析 `open.bigmodel.cn`(`EAI_AGAIN`),因此 data URL 进入后仍无法真正调用 GLM 视觉 API。
  - 要让端到端完全跑通,需给 zai-sidecar 配置出站网络/代理(如接入 `web-network` 或走 `egress-gateway`)。


- 客户端(Deerflow/DifyDSL/任何 MCP 客户端)**零改动、零新增直连**,
  一切仍经 hub relay,审计/限额链路不变。
- 不得打印/提交任何 token、API key;38 部署遵循 backup-first、只重建受影响服务。
