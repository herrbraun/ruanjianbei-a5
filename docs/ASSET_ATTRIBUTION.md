# 第三方数字人动作素材说明

## 自然待机循环

- 文件：`frontend/public/animations/chatvrm-idle-loop.vrma`
- 来源：[pixiv/ChatVRM 的 `idle_loop.vrma`](https://github.com/pixiv/ChatVRM/blob/main/public/idle_loop.vrma)
- 上游仓库：[pixiv/ChatVRM](https://github.com/pixiv/ChatVRM)
- 许可证：MIT License
- 文件校验（SHA-256）：`ace95ba6dcc0bdf2ed1081c002332b4184441117c8d543b6f642b3d2c5cf99be`
- 用途：游客端数字人在“待机”状态下播放的循环动作。

## Mixamo 讲解动作（本地比赛演示素材）

以下动作由项目操作者在自己的 Adobe Mixamo 账户内下载为“FBX Binary / Without Skin / 30 FPS / No Keyframe Reduction”，再使用 [fbx2vrma-converter](https://github.com/TK-256/fbx2vrma-converter)（MIT）转换为 VRMA：

| 页面状态 | Mixamo 动作 | 本地 VRMA 文件 | 播放方式 |
| --- | --- | --- | --- |
| 欢迎 | `Waving Gesture`（AJ Waving Gesture） | `welcome-wave.vrma` | 单次 |
| 指路 | `Pointing Gesture`（AJ Pointing Gesture） | `guide-point.vrma` | 单次 |
| 思考 | `Thinking`（Thinking While Standing） | `thinking.vrma` | 循环 |
| 讲解 | `Talking`（General Conversation） | `speaking.vrma` | 循环 |

- 存放位置：`frontend/public/animations/mixamo/`。
- 前端构建会通过 `frontend/scripts/copy-avatar-animations.mjs` 将整个 `public/animations` 目录镜像到 `dist/assets/animations`，与 FastAPI 的 `/assets` 静态托管兼容。
- 这些来自账户下载的原始/转换动作文件不提交到公开 Git 仓库，目录已被 `.gitignore` 忽略；比赛本机运行和打包时保留即可。
- 若换电脑或重新部署，请由拥有 Mixamo 使用资格的操作者重新下载并转换相同动作，再放回上述目录。不要将原始 FBX 或独立 VRMA 动作素材作为可下载资源再分发。
