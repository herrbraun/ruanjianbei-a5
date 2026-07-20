# 第三方数字人动作素材说明

## VRM 数字人模型

- 文件：`backend/uploads/avatars/*.vrm`（共 10 个）
- 制作工具：VRoid Studio 2.14.0
- VRM 作者元数据：`AI Tour Guide Team`
- 项目来源记录：团队在 VRoid Studio 中自制，没有记录使用 VRoid Hub、BOOTH 或其他第三方模型与付费纹理。
- 商用依据：VRoid Studio 官方允许个人和企业商业使用由正式版导出的模型及未标注特殊条款的内置素材；自行制作的纹理和发型网格权利归创作者。若后续加入第三方纹理、服装、发型或特殊许可素材，必须在本文件登记来源和授权条件后才能用于商业发布。
- 注意：VRM 内的作者和版权元数据只能作为项目声明，不能代替原始 `.vroid` 工程、制作记录或第三方素材授权凭证。正式商业发布前应保留这些证据并完成一次资产清单复核。

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
- 前端构建会通过 `frontend/scripts/copy-avatar-animations.mjs` 将整个 `public/animations` 目录镜像到 `dist/animations`；Vite 开发环境和 FastAPI 生产托管统一通过 `/animations` 访问。
- 转换后的动作随比赛项目仓库保存，确保换电脑和部署时能够还原展示效果；不得把原始 FBX 或独立 VRMA 文件作为单独素材包发布、销售或提供下载。
- 若仓库改为公开仓库或对外发行，需先重新确认 Adobe Mixamo 对当前分发方式的授权条件，必要时改用明确允许再分发的动作素材。
