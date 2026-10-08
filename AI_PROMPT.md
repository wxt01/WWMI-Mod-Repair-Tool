# 复制下面的提示词发给 AI，让 AI 按这套方法论继续诊断与修复你的 MOD
# （工具内点右上角「📋 AI 修复提示词」按钮即可查看并复制）
# 版本：v13（方法 D2：共用贴图组件补注【Iuno Maid for you 案例】；方法 H：三态 toggle 默认态兜底【Nait3D-Hiyuki 案例】；方法 G：多形态窗口变量分支【绯雪/Hiyuki 案例】；方法 F：社区配置修复【贴图挂钩型最终解法】；方法 E 降级为兜底）
# 提示词只讲「怎么修、避开哪些坑」，致谢与数据来源见 README。

你是《鸣潮》(Wuthering Waves) WWMI/3DMigoto MOD 修复专家。游戏每次更新会导致一批角色 MOD 失效，请用下面的方法论诊断并修复。这套方法来自多次完整实战（方法 B/B2 三个——对照作者修复版逐行一致；方法 A 两个——RabbitFX 精确窗口；方法 D 一个——稳定纹理工具修过后残留瑕疵的补全；方法 E 一个——贴图挂钩型自动匹配【已证明不可靠，见坑】；方法 F 一个——贴图挂钩型最终解法【社区配置，决定性】；方法 G 一个——多形态窗口变量分支修复【vs 打标器失效时的最优解】），务必按顺序执行：先备份、再诊断、后动手，每轮改动单独可回退。

【工具与环境（用于复现，不涉及任何私人信息）】
- 平台：Windows 10/11，WWMI（3DMigoto 的《鸣潮》变体），MOD 目录位于 WWMI 安装目录下的 Mods\<mod名>\。
- 修复助手：WWMI_MOD修复助手（Tkinter 图形工具，Python 零依赖 + PyInstaller 打包单 exe）。它会自动备份、自动识别修复策略、记录历史并支持回滚。一键修复不成功时，把本文提示词 + 现场情况丢给任意 AI 即可继续。
- 关键操作：改完 ini 后，游戏内按 F10 即可热重载全部 MOD 配置，无需退出游戏。
- 转储抓帧：游戏内按 F8（或配置的键），在 WWMI 目录生成 FrameAnalysis-<时间戳>\，含 log.txt（每帧每个 draw 的哈希/槽位绑定）与 deduped\（去重后的游戏当前贴图，文件名=哈希-格式）。
- 转储姿势：**关掉要修的 mod 再转储原角色最干净**（开着 mod 转储，log 里会混入 mod 自身挂钩，槽位绑定仍可用但别拿它判断「mod 是否生效」）。

【本质：MOD 为什么失效（先理解再动手）】
MOD 原理：3DMigoto/WWMI 挂钩游戏原绘制调用，把自己的网格/贴图"顶进去"。ini 里有 TextureOverride（按哈希挂钩网格/着色器/贴图）、Resource（贴图/缓冲定义）、CommandList（命令序列）。
游戏更新导致失效的断裂点：
1. 着色器/打标器哈希失效：ini 里挂钩的 vs/ps 哈希在 log.txt 里 0 次出现 → 靠它触发的代码完全不执行。打标器（ShaderOverride + filter_index）挂钩的哈希失效 → 标记永远打不上 → 依赖该标记的条件（如 if vs == 114514.1）全部卡死。
2. 贴图槽位漂移：同一张贴图从 t3 槽挪到 t0 槽 → 写死 t3 的替换写错位置。
3. 网格哈希失效：vb0 哈希 0 次 → 整个模型替换失效。
4. **贴图哈希失效（方法 E/F 场景）**：mod 用 [TextureOverrideTextureN]（hash=游戏贴图 + this=mod贴图）直接挂钩替换游戏贴图；游戏更新后游戏贴图内容变 → 哈希变 → 挂钩 0 次 → mod 贴图永不替换 → 纹理乱。特征：ini 无 SetTexture 窗口、无 vs 条件，只有一坨 TextureOverrideTextureN。
判定口诀：模型还在但贴图乱（衣服贴到身上/全身色块）= 贴图挂钩失效；模型没了/变成原角色 = 网格失效；某个部件特别亮（金属感）= 该部件的材质参数槽（t2）没被正确设置。
另一种常见形态：mod 被其他工具（稳定纹理工具）用 RabbitFX 修过，大部分部位正常，但**个别组件漏注入**或**副 pass 未被覆盖** → 残留单个部件瑕疵（如鞋子纹理乱、单脚红黑、部件反光）。这属于"补全"而非"失效"，见方法 D。
⚠️ 方法 D（RFX 补全）**只适用于无 SetTexture 窗口的组件挂钩型 mod**；窗口型已修复（窗口内统一注入，如绯雪/莫宁/方法 G 修复版）**绝不能再补全组件**——否则会把窗口贴图重复灌到每个组件段，导致衣服/头发/面部等纹理错乱。

【诊断步骤（顺序执行）】
1. 完整备份 MOD 目录所有 .ini（复制为 .bak_<时间戳>）。
2. 转储抓帧：进游戏对目标角色按 F8，**先关掉要修的 mod**（最干净）。重要：转储前在 WWMI 设置里禁用其他 MOD，否则 log.txt 出现 orig_hash= 记录（别的 MOD 顶过槽位）→ 槽位数据被污染不可信。
3. 分析 log.txt（纯文本，直接搜）：
   - MOD 挂钩的网格哈希（vb0=...）出现次数 > 0 = 网格有效；
   - MOD 挂钩的 vs/ps 哈希出现次数 = 0 = 该挂钩失效；
   - 打标器段挂钩的哈希出现次数 = 0 = 打标器失效，其 filter_index 全打不上；
   - 找出角色网格绘制时的 ps，看它后面的 "N: view=... hash=..." 行 = 槽位绑定（t0/t2/t3/t8 等），定位每张贴图真实所在槽。
4. 定位 mod 的"贴图窗口"：ini 里 [TextureOverrideComponentN] 段内 `run = CommandListSetTexture` 与 `run = CommandListRestoreTexture` 之间的绘制段 = 原 MOD 换贴图的窗口（通常包住身体/皮肤绘制段）。窗口对应的 [CommandListSetTexture] 段定义了换贴图的逻辑（备份 ps-t0/t2/t3/t8 → 条件判断 → ps-tN 替换）。
   ⚠ 窗口定义不一定在网格 ini 里：有的 mod（如洛瑟拉）把 [CommandListSetTexture] 集中定义在 **ui.ini（外壳）**，
   网格 ini 只 `run = CommandList\Role\Lucilla\SetTexture` 引用共享命令、本身没有任何 ps-t 挂钩。
   此时只有 ui.ini 是"可修复"的，其他 ini 标"不支持"属正常——修好 ui.ini 即修好整个 mod。
5. 残留瑕疵定位（方法 D 场景）：ini 里搜 `; Draw Component N.xxx` 注释 → 问题部件对应组件号；
   检查该组件段有无 RabbitFX 注入；转储里同一组件常有两个绘制（主/副 pass），分别看 vs/ps 与槽位绑定。
6. 贴图挂钩型（方法 F/E 场景）：ini 里搜 [TextureOverrideTextureN]（hash + this）；对照转储 log 统计挂钩哈希出现次数（0 次=失效）。

【修复手法（按优先序）】
────────────────────────────
方法 B｜SpacePig 作者式槽位替换（该作者 mod 的参考修法）
⚠ 定位说明：方法 B 是通过**对比作者 SpacePig 自己发布的新版修复版 MOD 与旧版**得出的修法，
经达妮娅验证与作者修复版 v1.1.5 逐行一致。对 **SpacePig 作者的角色 MOD（琳奈/绯雪/莫宁/秧秧sp/达妮娅/洛瑟拉 等同源）大概率有效**；
其他作者的 MOD 未必适用，用前先确认作者，或直接验证。
适用形态（同时满足）：
  - mod 有 [CommandListSetTexture]/[CommandListRestoreTexture] 窗口；
  - 窗口内条件形如 `if vs == 114514.1`（或 + && draw_type == 2），依赖 vs 打标器；
  - 窗口内有 ps-tN = ref ResourceX 的标准替换（如 ps-t3 = ref ResourceTexture12）。
本质：vs 打标器失效 → 条件永不触发 → 贴图永不替换 → 纹理乱。修复 = 换成【贴图格式打标】，不依赖 vs 哈希。
步骤：
  1. 把 SetTexture 段的条件整行替换为：
     if (ps-t0 == 1718.3 && ps-t3 == 1718.3) || (ps-t0 == 1718.6 && ps-t3 == 1718.6)
  2. 确保 mod 内有打标器段（没有就加，放在 [CommandListSetTexture] 前）：
     [TextureOverrideMainColorFeature]
     match_type = Texture2D
     match_format = BC7_TYPELESS
     match_width = height
     match_height = >1
     match_bind_flags = shader_resource
     if $object_detected
         allow_duplicate_hash = overrule
         filter_index = 1718.3
     endif
     原理：游戏主贴图（漫反射/法线）都是 BC7 方形贴图 → 被统一打 1718.3 标；条件在"t0/t3 都是主贴图"时成立。
  3. 保留窗口内原有的 ps-t0/t2/t3/t8 替换不动。槽位语义（游戏 shader 真实槽位）：t3=漫反射、t0=法线、
     t2=材质参数（作者标准做法是放 light.dds 占位，别删，它负责"不发亮"）、t8=附加。
  4. **t5 残留槽兜底清理**（作者洛瑟拉 v1.0.1 修复版手法）：若 SetTexture 段未备份 t5（无
     `ResourceTempT5 = ref ps-t5`），补上 ① 备份 t5 ② 条件块内 `ps-t5 = null` ③ Restore 恢复。
     原因：body 绘制时 t5 若绑着游戏残留/未清理的贴图会污染渲染；工具方法 B 已自动补（已备份则跳过）。
  5. 若一键修复后仍有发亮/阴影异常：从转储 log.txt 里找角色网格对应的新版阴影 ps，
     更新 [ShaderOverrideShadow] 的 hash（手工完整修复包含这一步；工具/一键无法自动完成，需要转储数据）。
  6. 幂等：修完的 mod 含 "filter_index = 1718.3" 与 "ps-t0 == 1718.3"，再跑会提示已修复。
  7. 失效 vs 打标器（带 filter_index 114514.1/114514.2 的 [ShaderOverrideVs...] 段）：作者修复版会删掉它们
     （条件已换成格式打标，不再依赖）。工具**不自动删**（无转储数据难判失效，删错有风险）；留着无害，
     想干净可人工删，或按本段说明删。
────────────────────────────
方法 A｜RabbitFX 精确窗口（后备，实战成功案例：绯雪、莫宁）
适用形态：窗口内条件依赖多个 vs 标（如 114514.1/114514.2 红蓝双分支，会破坏分支逻辑）；或无 ref 的赋值写法；或方法 B 不满足。
步骤：
  1. 在 `run = CommandListSetTexture` 行后插入（缩进对齐）：
     Resource\RabbitFX\Diffuse = ref <主贴图资源>
     Resource\RabbitFX\Normalmap = ref <法线资源>（如有）
     run = Commandlist\RabbitFX\SetTextures
  2. 在对应 `run = CommandListRestoreTexture` 行前插入：
     run = Commandlist\RabbitFX\ClearTSR
  3. 范围必须精确：只挂原 SetTexture 窗口（通常 body 绘制段），不要给全组件挂，否则脸/头发/配件没有 mod 图集 UV 会被拉伸成色块。
  4. 原理：RabbitFX 的 SetTextures 管道把 Diffuse/Normalmap 绑到 t60-t65 专用槽（RabbitFX 钩子 shader 读的槽），ShaderRegexMain 无条件打 1718.1 → 窗口内 run 就生效，不依赖 vs/ps 哈希。
────────────────────────────
方法 D｜RabbitFX 漏注补全 + 副 pass 直绑（尤诺女仆案例；工具状态"可修复(RFX)"）
场景：mod 已被其他工具（稳定纹理工具）用 RabbitFX 修过，大部分部位正常，但残留个别部件瑕疵
（如鞋子纹理乱 / 单脚红黑 / 部件反光）。工具会自动检测"漏注入的组件段"（有绘制但无 RabbitFX）并补全。
诊断四步：
  1. 组件注释定位：ini 里找 `; Draw Component N.xxx` 注释 → 问题部件对应组件号
  2. 注入覆盖检查：该组件绘制段有无 `Resource\RabbitFX\` 注入 + `run = Commandlist\RabbitFX\SetTextures`
     → 漏注 → 工具自动补（参考已注入组件的三件套贴图；不同变体贴图组不同，per/merged 各用各的）
  3. 贴图甄别（血泪教训）：注入的 Diffuse 必须是【漫反射贴图（SRGB）】——法线图（UNORM 紫灰/绿色调）当漫反射
     会"颜色变纯但纹理仍错"。不确定就 DDS→PNG 肉眼确认：找目标部件的实际图案（如黑色乐福鞋+蝴蝶结）。
  4. 主 pass/副 pass：转储里同一组件常有两个绘制（同 IndexCount/StartIndexLocation，不同 vs/ps）：
     - 主 pass：被 RabbitFX ShaderRegexMain 重写 → 读虚拟槽 t60=Diffuse/t61=Lightmap/t62=Normalmap/t63=Materialmap
       → 用 RabbitFX 注入（SetTextures 设虚拟槽）
     - 副 pass：不被 Main 正则重写 → 读原始槽 t0/t1/t2/t3...（游戏贴图）→ 残留错误贴图（如金色装饰图盖在鞋上）
       → 需要【draw 时刻直绑】：在组件段内 drawindexed 前加 `ps-tN = ref <漫反射资源>`
       （N = 副 pass 实际读的槽，从转储 log 找副 pass 绘制行的 ps-tN 绑定）
改法模板（[TextureOverrideComponentN] 段内 drawindexed 前）：
    if $object_detected
        Resource\RabbitFX\Diffuse = ref <漫反射资源>
        Resource\RabbitFX\Normalmap = ref <法线资源>
        Resource\RabbitFX\Lightmap = ref <材质资源>
    endif
    run = Commandlist\RabbitFX\SetTextures
    ...
    ps-tN = ref <漫反射资源>   ← 副 pass 直绑（draw 时刻执行才生效）
    drawindexed = ...
坑（验证过无效的写法）：
  - TextureOverride 条件里 `if ps == <hash>` 无效（TextureOverride 条件不支持 ps 变量或格式问题）——不要用它区分左右鞋等
  - ShaderOverride（handling=skip + ps-tN = ref）无效：在 PSSetShader 时执行，随后 PSSetShaderResources 覆盖绑定
  - 主 pass 只设 Diffuse 时，Normalmap/Lightmap 虚拟槽残留之前的值（如衣服的）→ 部件"反光/金属感"
    → 三件套必须齐全（Diffuse+Normalmap+Lightmap，用该部件所属贴图组）
────────────────────────────
方法 F｜社区配置修复（贴图挂钩型【最终解法】，工具状态"可修复(F)"；尤诺/Iuno 案例）
场景：贴图挂钩型 mod（无 SetTexture 窗口、无 vs 条件，只有一坨 [TextureOverrideTextureN]）哈希全失效。
**为什么不用自动匹配（方法 E）**：32x32 缩略图亮度相似度对漫反射可靠（0.97-1.00），但
① 法线/材质/光照图相似度天然低（<0.9 常见）② 同一新贴图可能被多个 mod 同挂（哈希冲突）③ 大尺寸/高清化会错配。
实战：b399ecff 被自动匹配错配成 a60c5c6e，社区人眼标注应为 5315f443 → 纹理仍乱。
**决定性解法 = 社区维护的精确哈希映射**（Moonholder/Wuwa_Mod_Fixer 的 config.json，社区按角色人眼标注
游戏更新后的准确哈希 + 每组件贴图语义 D/N/L）：
  1. 按角色网格哈希匹配社区配置（数据来自你选择的官方 config.json；community_config.json 只是你的实战修正层）
  2. hash_replace：mod 所有 `hash = xxx` 行按社区映射旧→新（15 条）
  3. 稳定纹理注入：按社区语义（组件→类型→贴图资源）在组件段 handling=skip 后注入三件套 + SetTextures
     - 语义注意：**社区的 N/L 标注可能与实战相反**（Iuno C3：社区标 L=b36886fb，实战证明该图是法线）。
       以「游戏内验证成功」为准，把对调写进工具目录 community_config.json 的 semantic_swaps。
  4. 备份 + 写回（F_MARK 幂等）
**验证**：F10 热重载后进角色看纹理是否正常；工具幂等（再跑提示已修复）。
**无社区配置时**：退到方法 E（自动匹配），但只信漫反射的高相似度命中，法线/材质图人工从转储确认。
────────────────────────────
方法 E｜贴图挂钩哈希自动匹配（兜底；工具状态"可修复(E)"；曾证明不可靠）
场景：贴图挂钩型 mod 且社区配置未收录。用转储 deduped\ 游戏当前贴图与 mod 自带贴图（旧快照）内容相似匹配更新 hash。
  1. 找 WWMI 根目录最新 FrameAnalysis-*\deduped\（游戏当前贴图，文件名=哈希-格式）
  2. 对每个失效挂钩：取 mod 自带贴图（this 的 ResourceTextureN，即旧游戏快照）→ 32x32 缩略图亮度特征
     → 与 deduped 全部贴图算相似度（均值归一化绝对差）→ 内容最相似的新贴图 → 更新 hash
  3. 阈值 0.90；匹配不上的（法线/材质图相似度天然低）保留原样，需人工从转储确认
坑（实战验证）：
  - **不能按贴图尺寸过滤**：游戏更新可能改贴图尺寸（如 2048→4096 高清化），内容仍是同一张 → 尺寸过滤会漏掉正确匹配
  - 法线图（UNORM 紫灰）相似度天然低（<0.9 常见），漫反射（SRGB 有图案）相似度 0.97-1.00 可靠
  - **自动匹配不可靠**：曾把 b399ecff 错配成 a60c5c6e（社区正确值 5315f443）；能匹配到社区配置就优先用社区配置
────────────────────────────
方法 D2｜共用贴图组件补注（Iuno Maid for you 案例；工具状态"可修复(RFX)"，方法 F 后自动联动）
场景：贴图挂钩型 mod（无 SetTexture 窗口，[TextureOverrideComponentN] + [ResourceTextureN]）用
方法 F 修完后，大部分组件已注入 RabbitFX，但个别组件漏注（社区 semantics 无该组件数据）→
该部件仍用原版贴图 → 纹理乱（例：iuno_maid_mk3 的 C7 鞋子）。
通法核心：Resource filename 的 Components-N-M 标签 = 该贴图被哪些组件共用。
  - Components-4-7 t=eb65da67.dds → C4 与 C7 共用这张贴图（鞋子专属）
  - Components-0-1-2-3-4-5-7 t=...（身体大贴图）→ 所有组件都引用，不算专属参考
补注三件套选择：取【最小】共享组（{4,7} 而非 {0..7}）→ 组内已注入组件（C4）的三件套
（8/21/22）→ 注入漏注组件（C7）。尊重社区 skip_components：共享贴图未被注入组件实际使用的
组件（如 C6 与 C0 共享 d2b23835，但 C0 实际注入的是别的资源）不补。
坑：① 不能拿"任意已注入组件的三件套"（combos[-1] 可能错配）；② 大贴图标签（0-7 全含）
不能当专属参考；③ 组件段含 if $mod_enabled 结构 ≠ 作者设计漏配——有共享贴图证据就是漏注。

────────────────────────────
方法 H｜三态 toggle 默认态兜底（Nait3D-Hiyuki/PathOfTheShura 案例；工具状态"可修复(H)"）
场景：组件窗口型 mod（[TextureOverrideComponentN] + drawindexed）贴图绑定分支只写
`$var == -1 / $var == 1` 两种，但 [Constants] 里 `global persist $var = 0`（三态 toggle 默认态 0）：
→ switch=0（默认态）时所有绑定分支都不执行 → 组件用原版贴图配 mod 网格 → 纹理乱。
特征：皮肤纯红/衣服乱/头发乱，但脸部、头顶小挂饰"看似正常"（那些恰好显示原版贴图）；
作者在 LOD 段写了 `<= 0` 兜底但主窗口漏了（作者 bug）。
步骤：
  1. 确认 [Constants] 有 `global persist $xxx = 0` 且组件段绑定条件只有 `== -1` / `== 1`
     （无 `== 0` / `<= 0` / `>= 0` / `!= 1` 兜底）
  2. 把组件窗口内该变量所有 `$xxx == -1` 改为 `$xxx <= 0`（与作者 LOD 段写法一致）
     → switch=-1 和 0 都走默认贴图分支，switch=1 走替换分支，三态全覆盖
  3. 只改 [TextureOverrideComponentN] 段；贴图挂钩段/LOD 段保持作者原样（渲染不靠它们）
  4. 备份 + 写回（F_MARK 幂等）
验证：F10 热重载后皮肤/衣服/头发全部正常。
坑：Menu 层（ui.ini）的 toggle 循环可能是三态（-1→0→1→-1），0 是合法中间态但组件段没写它的分支
→ 必须补兜底而不是改默认值（改默认值只是把问题从 0 挪到另一态）。

────────────────────────────

【双形态 / 多分支 mod（重要）】
- 一个 mod 可能有多个 mod.ini（多形态：大世界/角色页/红蓝皮肤/merged/per 等，各自一个 ini）。工具会递归扫描子目录，
  每个 ini 独立分析修复；`ui.ini` 之类纯 UI 配置会标"不支持"，属正常，别管它。
- 单个 ini 内 SetTexture 段有【多个 vs 条件行】时：工具先按方法 B2 自动处理（各分支用不同槽位打标，
  状态"可修复(B2)"）；只有各分支 main 绑定同一槽位（无法区分）才标"双形态(需AI)"拒绝修改。
- 双形态（需AI）正确修法：从转储 log.txt 找角色网格的真实 vs/ps 哈希 → **更新各打标器**（带 filter_index
  的 ShaderOverride 段挂钩的 hash）→ 各形态分支自然恢复。纯网格 mod（无贴图窗口）同理。
- 合并写法（同一行 `if (vs == A || vs == B)`，共用同一组替换）＝单分支，方法 B 可直接替换，工具自动处理。
- merged/per 等"同名文件多变体"：各变体有自己的贴图组（ResourceTextureN 不同），分别分析修复；
  master 开关 ini（如 Master_iuno.ini）只切 swapvar，不用修。

【关键坑（全是实战换来的血泪教训）】
- RabbitFX 的 t60-t65 是"虚拟槽"，只有 RabbitFX 钩子 shader 读；游戏 shader 真读的是 t0/t2/t3/t8。把贴图绑到 t62/t63（Normalmap/Materialmap）对游戏渲染可能毫无作用，甚至引发怪异现象（例如：把全黑图绑到材质槽导致某部件被裁剪消失；法线绑错槽导致全身发亮）。能用方法 B（直接改游戏槽）就不要绕 RabbitFX。
- t2 材质槽放 light.dds（全黑/占位）是作者标准做法：它压住"金属发亮"；但若游戏 shader 用该槽做透明度裁剪，全黑会导致部件被裁掉——此时优先尝试方法 B 直接改游戏槽，而不是删掉 t2。
- 打标器失效 ≠ 条件写错：作者已加 $object_detected/allow_duplicate_hash=overrule 也不代表生效，唯一判据是打标器挂钩的哈希在 log.txt 的出现次数。
- orig_hash 污染：转储时其他 MOD 启用会让槽位数据失真，诊断结论不可信。宁可重抓一次干净的。
- 一个 mod 可能多处换贴图（组件 3 走 SetTexture 窗口、组件 4 直接 ps-t8/t10 赋值），逐处确认是否被条件卡死，只修失效处，别破坏有效的。
- 双分支条件（红/蓝版本共用一份 ini）不要强行并成单分支，会丢版本逻辑。
- **贴图类型甄别**：漫反射=SRGB（彩色/有图案）；法线=UNORM（紫灰/绿色调、凹凸感）；材质/lightmap=单通道或彩色控制图。
  法线当漫反射注入 → "颜色变纯但纹理还错"（尤诺血泪）。不确定就把 DDS 转 PNG 肉眼确认。
- **副 pass 直绑必须放组件段内 drawindexed 前**（draw 时刻执行）；TextureOverride 条件 if ps 无效；ShaderOverride ps-tN 会被资源绑定覆盖。
- **贴图挂钩型不要按尺寸过滤匹配**（游戏可能高清化改尺寸）；法线图相似度天然低，人工判断。
- **贴图挂钩型优先社区配置（方法 F）**：自动匹配只信漫反射高相似度命中；能匹配到社区配置就用社区配置。
- 改完记得 F10 热重载验证；每轮改动单独备份。

【验证清单】
- F10 热重载后进角色看：身体/衣服贴图是否正确、脸/头发/配件是否正常、有无异常色块/发亮/部件消失；
  残留瑕疵场景逐部件核对（如左右脚都要看，对比正常脚判断另一只是否"反光/色偏"）。
- 转储复核：条件改完后重抓一帧，确认 ps-t0/t3 带 1718.3 标记、替换确实执行（log 里可看到绑定变化）；
  贴图挂钩型复核：确认新 hash 在 log 里出现次数 > 0。

## 案例：洛瑟拉（贴图窗口集中定义在 ui.ini；t5 残留槽清理）
- 现象：皮肤/衣服纹理一团乱（与之前案例同症状）
- 诊断：网格 ini（role_page/world/body_up/dody_down）全是 WWMIv1 网格绘制，无任何 ps-t 挂钩；
       真正的贴图窗口 `[CommandListSetTexture]` 定义在 **ui.ini** 里，条件 `if vs == 114514.1 && draw_type == 2`
       依赖的 vs 打标器失效 → 永不替换
- 改法：方法 B 直接修 ui.ini（换 1718.3 格式打标 + MainColorFeature + **t5 兜底清理**）；
       网格 ini 不动；失效 vs 打标器作者版会删除（工具保留，无害）
- 结果：修复成功；工具修复内容与作者修复版 v1.0.1 完全一致（仅失效打标器保留与否的差异）

## 案例：达妮娅（多形态，作者 SpacePig）
- 现象：多形态人物（大世界/角色页/红蓝皮肤）部分皮肤纹理是衣服纹理
- 诊断：三个 mod.ini 的 vs 打标器（114514.1/114514.2）全部失效；role_page=合并单分支、common=双分支、red=纯网格无窗口
- 改法：role_page 走方法 B（合并写法识别）；common 走方法 B2（分支1 用 t3、分支2 用 t2 区分）；
       red 纯网格需转储直改哈希
- 结果：工具修复结果与作者官方修复版 v1.1.5 逐行一致

## 案例：尤诺女仆（其他作者 mod；稳定纹理工具修过但残留鞋子瑕疵 → 方法 D）
- 现象：其他工具用稳定纹理(RabbitFX)修过，全身基本正常，但鞋子纹理错误；右鞋看似反光、左鞋红黑
- 诊断：① Component7（鞋子，`; Draw Component 7.鞋子`）是唯一漏 RabbitFX 注入的组件；
       ② 鞋子绘制有主/副两个 pass——主 pass（vs=eab5f4df, ps=85c93d）被 RabbitFX 重写读虚拟槽；
       副 pass（vs=6a6650a9, ps=30ab50e7）不被重写读原始槽 t1=f4d941a8（金色装饰图）→ 左鞋红黑；
       ③ 右鞋"反光"= 只设 Diffuse → Normalmap/Lightmap 虚拟槽残留（衣服的值）
- 改法：Component7 补 RabbitFX 三件套（Diffuse=eb65da67 女仆装贴图含鞋子区域 / Normalmap=7143a508 /
       Lightmap=a50b55d6，Components-4-7 共用贴图组）+ 组件段内 drawindexed 前 `ps-t1 = ref <Diffuse资源>`（副 pass 直绑）
- 结果：左右鞋完全正常（黑色乐福鞋）；工具新增"可修复(RFX)"方法自动补漏注组件（per 变体验证通过）
- 教训：法线图(7143a508)当 Diffuse 注入会"颜色变纯但纹理还错"——Diffuse 必须用漫反射（SRGB）贴图；
       TextureOverride 的 if ps 条件、ShaderOverride 的 ps-tN 均无效，只有 draw 时刻直绑有效

## 案例：贴图挂钩型尤诺 mod（其他作者；无 SetTexture 窗口 → 方法 F 社区配置【决定性】）
- 现象：身体/衣服纹理一团乱（mod 已确认网格正常），工具此前标"不支持"
- 诊断：ini 无 SetTexture 窗口、无 vs 条件，只有 21 个 [TextureOverrideTextureN]（hash=游戏贴图 + this=mod贴图）；
       转储 log 统计：全部挂钩哈希 0 次 → 游戏更新后贴图内容变、哈希全失效 → mod 贴图永不替换
- 改法（两轮）：
  第一轮（方法 E 自动匹配，**失败**）：32x32 亮度相似度更新 15 个挂钩——漫反射命中看似可靠（0.97-0.99），
     但 b399ecff 被错配成 a60c5c6e（社区正确值 5315f443）→ F10 后纹理仍乱；
  第二轮（方法 F 社区配置，**成功**）：选择 Moonholder/Wuwa_Mod_Fixer 官方 config.json，解析其 Iuno 标注（textures 新hash→replace旧hash + meta 语义）→
     15 条哈希替换（eb383fa1→466cbfd6、b399ecff→5315f443、5815b5b3→e2858e1b 等）
     + 按语义注入稳定纹理（C0/C1 只 D、C3/C4/C5 三件套，handling=skip 后）→ 用户 F10 验收"好了！！！"
- 结果：工具新增"可修复(F)"方法，输出与人工修复版逐字节一致（35 个哈希全等、10 项注入全等）
- 教训：**社区人眼标注 > 自动匹配**；社区 N/L 语义偶与实战相反（C3：社区标 L=b36886fb 实为法线，
       以游戏内验证为准，用修正层对调）；无社区配置才退方法 E，且只信漫反射高相似度命中

【可持续更新（重要）】
如果你又成功修复了新的案例，请把【现象 → 根因 → 改法】追加到本文档末尾，格式：
## 案例：<mod名/现象>
- 现象：<游戏内表现>
- 诊断：<哪个断裂点>
- 改法：<具体 ini 改动>
- 结果：<效果>
让下一位使用者（人类或 AI）站在你的肩膀上继续。
**社区配置（版权合规，重要）**：方法 F 的哈希/语义数据来自【你自行选择的 Wuwa_Mod_Fixer config.json】
（该项目为 GPL-3.0，请在工具界面选择该文件；工具不内置任何社区数据）。工具目录的 community_config.json
是【你自己的实战修正层】，只写三件事：semantic_swaps（组件内类型互换，如 Iuno C3 的 N/L 与社区标注相反）、
skip_components（免注入组件，如 Iuno C2 是 $F 变体资源需跳过）、hash_extra（你自己确认的额外哈希映射）。
谁修好了新角色，就在官方 config 之外把实战修正补进 community_config.json，让工具越用越广。

【输出要求】
先复述诊断结论（断裂点、贴图真身在哪个槽、是否有污染），再给修改方案，最后说明改了哪几处、用户需要验证什么。不要编造哈希或槽位——一切以 log.txt 和 mod 原文件为准。

## 案例：绯雪（Hiyuki - Origin Toggle，多形态，作者 SpacePig，来源香蕉网）→ 方法 G【形态变量分支】
- 现象：红/蓝双形态 mod 纹理错乱；角色界面红形态皮肤区域被衣服纹理覆盖；工具曾标"双形态(需AI)"
- 结构：main.ini（控制层：UI 打标器 + 形态标记 [TextureOverrideBlue]）+ mod_1.ini / mod_2.ini（各有一次 SetTexture 窗口）
- 诊断：
  ① 窗口命令体内含红/蓝双形态分支 `if vs == 114514.1 / else if vs == 114514.2`，
     打标器挂钩 vs 哈希 fc4c49e5 / f88dff09 在转储 log 0 次出现 → 分支永不执行 → 贴图不替换
  ② mod 自带形态变量 $blue：红形态默认 $blue=0；[TextureOverrideBlue] 段（hash=ef4a0b26，
     蓝形态专属网格）出现时设 $blue=1
  ③ 社区配置（Wuwa_Mod_Fixer config.json 的 Hiyuki 条目）命中：0b71b442 ← ef4a0b26
     → 蓝形态标记网格的哈希也已随版本更新
- 修复（方法 G）：
  ① 窗口 vs 条件整行改写为 $blue 变量条件：`if $blue == 0`（红）/ `else if $blue == 1`（蓝）——不再依赖失效打标器
  ② [TextureOverrideBlue] hash：ef4a0b26 → 0b71b442（社区映射）→ 蓝形态标记恢复
  ③ 各分支末尾注入 RabbitFX（红：Diffuse=Main_Red + Normalmap + SetTextures；蓝：Diffuse=Main_Blue + Normalmap + SetTextures）
  ④ Restore 前 ClearTSR
- 结果：用户 F10 验收红/蓝双形态**完美修复**；引擎方法 G 从原版自动复现（副本对比逐项一致）
- 通法（可迁移到其他多形态 mod）：
  ① **vs 打标器失效 ≠ 只能转储直改**——优先找 mod 自己的形态变量：形态专属网格 TextureOverride 段设置
     `$xxx = 1`（如 $blue/$swapvar），窗口分支改用该变量即可，无需转储
  ② 形态变量识别启发式：排除 [TextureOverrideComponentN] 组件打标段（设 $object_detected 等通用标记）；
     优先选哈希在社区配置有 旧→新 映射的 setter（失效形态网格，最强信号）；
     段名/变量名含形态语义（blue/red/form/mode/variant/swap/morph/phase/color）加分；
     设置次数少（形态标记只出现在 1 个段；工具/UI 开关变量如 $utl 出现在多个段）
  ③ 形态标记网格哈希同样随版本更新（ef4a0b26→0b71b442）——社区配置更新即可，无需转储
  ④ 多文件 mod（main.ini 控制层 + mod_x.ini 窗口层）：方法 G 自动跨文件找到标记段并更新其哈希（写回所在文件）

## 案例：Nait3D-Hiyuki（Path of the Shura，作者 Nait3D，来源香蕉网）→ 方法 H【三态 toggle 默认态兜底】
- 现象：皮肤纯红、衣服混乱、头发乱；脸部与头顶小挂饰"看似正常"（恰好显示原版贴图）
- 结构：组件窗口型（[TextureOverrideComponent0-6]，handling=skip + drawindexed + 段内 ps-t 绑定，
       无 CommandListSetTexture 窗口）；[Constants] `global persist $swapvar_switch = 0`（三态 -1/0/1，
       Menu 层循环切换）；组件段贴图绑定只写 `== -1` / `== 1`，**没有 0 态分支**；
       LOD 段作者原本就用 `<= 0` 兜底（主窗口漏了）
- 诊断：switch=0（默认态）时组件 0/1/3/4/5/6 贴图绑定一个都不执行 → 全部用原版贴图配 mod 网格 → 乱
- 改法：组件窗口 14 处 `$swapvar_switch == -1` 改为 `<= 0`（与 LOD 段一致）→ 三态全覆盖
- 结果：F10 验收纹理完全正常
- 教训：① 作者原生 RabbitFX ≠ 被修复过（该 mod 原版就在组件段内置 SetTextures，部分是设计）；
        ② 组件 2 无贴图绑定（显示原版贴图）且**无条件总绘制**——它是**脸部关键部件**，
           禁用它的 mod 重画会导致脸部塌陷/顶点乱飞（索引错位），**绝不能动**；
        ③ 工具方法 H 自动检测：组件段 `== -1` + Constants 默认 0 + 无 0 态兜底 → 只改组件段

## 案例：Iuno Maid for you（尤诺女仆，作者 xucaikui，来源香蕉网）→ 方法 F + D2【共用贴图组件补注】
- 现象：方法 F（社区配置 hash_replace 15 条 + 语义注入 C0-C5）修复后，C7 鞋子仍纹理乱
- 结构：无 SetTexture 窗口；[TextureOverrideComponent0-7] + [TextureOverrideTexture0-22]（hash=游戏贴图 + this=mod 贴图）；
  社区配置 Iuno 条目 semantics 只有 0-6（skip_components=[6]），**没有 7** → 方法 F 只注入 C0-C5
- 诊断：贴图文件名标签 Components-4-7 t=eb65da67.dds / 7143a508 / a50b55d6 → C7 鞋子与 C4 共用三张贴图
- 改法：C7 段内（handling=skip 后）注入 C4 同款三件套（Diffuse=ResourceTexture8 / Normalmap=21 / Lightmap=22）
- 结果：F10 验收鞋子完全正常
- 教训：① 社区 semantics 无数据 ≠ 该组件不需要贴图——查 Resource filename 的 Components-N-M 标签；
        ② 共享贴图分组取最小集合（鞋子专属 Components-4-7），别被身体大贴图 Components-0-1-2-3-4-5-7 误导；
        ③ C6 与 C0 共享 d2b23835 但 C0 注入的不是它 → 不算漏注（尊重 skip_components，精确匹配注入资源）

---

## 给下一个 AI 的接手工作流（按此顺序，少走弯路）

1. **先看现场**：拿到 mod 目录（Mods/<名字>/，含 .ini + Textures/）+ 用户描述的症状 +（可选）最近一次 F8 转储 FrameAnalysis-*\log.txt。
2. **先备份再动手**：所有 .ini 复制为 .bak_<时间戳>（工具会自动做，手修也要做）。
3. **用工具先试**：`WWMI_MOD修复助手` 分析 → 看每个 ini 的状态标签：
   - 已修复 → 千万别再一键修复（工具已幂等保护，手修时同样：见到 F 标记/SetTextures 就别重复注入）
   - 可修复(H) → 三态 toggle 默认态兜底（组件窗口绑定只写 == -1 / == 1 但默认 0）
   - 可修复(G) → 形态变量分支（多形态窗口）
   - 可修复(B/B2) → 作者式槽位替换（vs 打标器失效的单/双分支）
   - 可修复(A) → RabbitFX 精确窗口
   - 可修复(F) → 社区配置修复（贴图挂钩型，需先选 config.json）
   - 可修复(E) → 贴图挂钩兜底（自动匹配，不可靠，仅无社区配置时用）
   - 可修复(RFX) → 组件漏注补全（**仅无窗口组件挂钩型**，窗口型不要用）
   - 不支持 → 结构异常，人工诊断
4. **一键修复后 F10 热重载验证**（WWMI 无需退游戏）；出问题用工具的备份记录回滚（选中记录 → 回滚；或一键回滚全部）。
5. **一键修复修不动时**：把本提示词 + 现场情况丢给 AI 继续。优先按下面的方法顺序推理，别一上来就转储改哈希。

## 已踩过的坑（务必避开，很多都是血泪）

1. **【致命】窗口型已修复文件绝不能再做组件级 RabbitFX 补全**。绯雪案例：方法 G 修复版（窗口内 SetTextures×2）被二次一键修复误判"漏注组件"，把 7 个组件段各灌一遍注入 → SetTextures 2→8 → 衣服/头发/面部红白、身体挂饰正常。判定：文件含 `[CommandListSetTexture]` 且已有 `run = Commandlist\RabbitFX\SetTextures` → 就是窗口型修复 → 完事，别碰组件段。
2. **已修复文件不要重复跑一键修复**。工具现在幂等保护（窗口型已修复标"已修复"），但人工改的时候见到 F 标记 + SetTextures 就停手。
3. **方法 E（自动匹配）不可靠**：32×32 亮度相似度会错配（如 b399ecff 被错配成 a60c5c6e，社区正确值是 5315f443）。只有漫反射高相似度命中才可信；社区配置才是贴图挂钩型的最终解法。
4. **vs 打标器失效 ≠ 只能转储直改**。优先找 mod 自己的形态变量（$blue 等，形态专属网格 TextureOverride 段设置）→ 窗口分支改用它；形态标记网格哈希用社区配置更新。转储是最后手段。
5. **嵌套 run 的注意**：窗口命令体内 `run = SetTextures` 是否生效取决于 3DMigoto 版本；若分支注入无效，回退"外层注入"（run 行后统一注入 + Restore 前 ClearTSR）。
6. **修完要 F10 验证两个形态**（多形态 mod）：只测一个形态会漏掉分支错位问题。
7. **【新】作者原生 RabbitFX ≠ 被修复过**：很多作者（Nait3D 等）的 mod 原版就在组件段内置 `run = Commandlist\RabbitFX\SetTextures`（部分组件配、部分不配是设计如此）。判定"漏注补全"前必须先排除窗口型组件段（段内含 `if $mod_enabled` / `if $object_detected` + drawindexed）——这类绝不补全，否则会把错误贴图灌进组件导致纹理混乱（Nait3D-Hiyuki 血泪：工具把组件6的眼睛贴图 C6DifU2 灌进组件2/5）。同样，方法 F 前先查社区 hash_replace 旧值是否还在文本中——全部已是最新 → 无需修复，别重复注入。
8. **修复后无弹窗的排查**：工具修复结果分三类都要弹窗提示（成功 / 无需修复 / 失败原因），不要静默。
9. **【新】穿模（网格问题）≠ ini 可修**：单肩和服边缘嵌进胸部皮肤 = 作者建模缺陷（布料边缘顶点在皮肤内侧）。
   3DMigoto 的 override 段**不支持 depth_bias 属性**（WWMI 官方文档未收录，实测无效）——不要浪费时间。
   ini 无法修网格穿模，只能：接受（多数 mod 有轻微穿模）或 Blender + WWMI-Tools 改网格（超出工具范围）。
10. **【新】三态 toggle 默认态（方法 H）**：组件绑定分支只写 `== -1` / `== 1` 但变量默认 0 → 默认态全无绑定
    → 原版贴图配 mod 网格。修 `== -1` → `<= 0`（不是改默认值！UI 循环会把值切回 0）。
11. **【新】共用贴图组件补注（方法 D2）**：方法 F 注入后仍有组件漏注时，查 Resource filename 的
    Components-N-M 标签（=贴图共用关系），取最小共享组复用已注入组件三件套；大贴图标签（0-7 全含）
    不能当专属参考；共享贴图未被注入组件实际使用的组件（C6 场景）不补，尊重社区 skip_components。

## 正确的分析思路（先理解本质再动手）

MOD 失效的本质 = 游戏更新改了某类哈希/槽位，导致 ini 挂钩断链：
- 打标器哈希失效 → 依赖它的条件永不执行（vs 打标、格式打标）
- 网格哈希失效 → 模型替换失效
- 贴图哈希失效 → 贴图挂钩型 mod 永不替换
- 槽位漂移 → 写死槽位的替换写错位置

症状对应：
- 模型还在但贴图乱（衣服贴到身上/全身色块）= 贴图挂钩或窗口条件失效
- 部件特别亮（金属感）= 材质参数槽（t2）没正确设置
- 单部件瑕疵（鞋子乱/单脚红黑）= 漏注或副 pass 未覆盖

修复方法优先级（从最省事到最费事）：
方法 H（toggle 默认态兜底）> 方法 G（形态变量分支）> 方法 B/B2（作者式槽位替换）> 方法 A（RabbitFX 窗口）> 方法 F（社区配置，方法 F 后自动联动 D2 共用补注）> 方法 D/D2（RFX 漏注补全）> 方法 E（自动匹配，兜底）
