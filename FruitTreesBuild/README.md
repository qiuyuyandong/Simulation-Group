# FruitTreesBuild

单株苹果树、橙子树素材构建项目。使用项目自带的 Windows Blender 5.2，支持现有 Windows Python 3.9+ 或 WSL specdec 启动，不需要在解释器中安装 bpy。

## 日常只运行三个脚本

| 工作 | 修改配置 | 直接运行 |
|---|---|---|
| 生成苹果树 | configs/apple_tree.json | generate_apple_tree.py |
| 生成橙子树 | configs/orange_tree.json | generate_orange_tree.py |
| 生成素材级 metadata | configs/export_metadata.json | generate_metadata.py |

在 PyCharm 中选择对应运行配置，或右键对应脚本运行。Parameters 参数栏保持空，工作目录选项目根目录。
配置保存后再运行，无需修改 Python 源码。三个入口与输出目录没有改变。

### 1. 构建素材

修改对应 JSON 的 seed、leafCount、fruitCount、treeHeight、trunkHeight、trunkDiameter 等。
苹果配置 fruit 保持 apple，橙子配置 fruit 保持 orange，固定入口会拒绝错配。
generator=auto 时，苹果使用 Space Tree、橙子使用 Sapling；两种算法和果柄连接方法均保留。
苹果树新增 branchUplift（外层枝条向上抬升量）、branchAngleMin（分叉开张角下限，默认 120°）、
heightTaper（高处枝条额外收细比例）和 leafSpacing（叶片碰撞代理之间的最小间隙）。
branchAngleMin 以“子枝与母枝反向延长线的夹角（开张角）”计；120° 表示子枝相对母枝前进方向
折转不超过 60°，同时保持向上。若要改的是两子枝之间的夹角，需要另行定义并调整求解器。
苹果叶片现在按实际枝干表面放置，并做叶片-枝干、叶片-叶片、叶片-果实、果实-枝干和果实-果实检查；
检测使用保守几何代理，不是完整三角面相交证明。3000 片叶在默认配置下可行，过密时会明确报错而不是静默丢弃。
苹果木质部改为“一条连续树干管 + 分枝管 + 喇叭形枝领”，不再用 Skin 按分枝切开树干；
生成时先做枝-干胶囊检查，再用三角化 BVH 检查枝管与树干的真实面重叠，超差会推动枝段让开或直接报错。
`metadata.json` 的 `structure.branch_trunk_intersection_count` 和
`structure.branch_trunk_mesh_intersection_count` 应为 0。
橙子仍使用 Sapling 算法，但采用低分叉、较舒展的柑橘树形预设，固定三级分枝；seed 仍会改变具体枝条形状。
想生成不同树形要修改 seed；只换文件夹编号不会改变树形。

橙子默认树高 3.2 m、裸干段 0.5 m、枝干中心线冠幅目标 3.2 m、1600 片约 10.5 cm 叶片、80 个果实。
这些是参考形态的建模目标，不是照片实测或品种标定。crownWidth 只控制枝干冠幅，叶果可能使最终外观范围略大。
橙子叶片带三维叶柄，按实际枝条表面放置；先放果实，再对叶片面片做空间避让。
leafFruitClearance 默认 0.006 m，对实际果实几何的保守包络增加间隙；调大将更难放下同样数量的叶片。
这避免几何穿入，不保证任何相机角度都无遮挡，也不是碰撞代理。规则与限制见 docs/orange_tree.md。

运行对应脚本后，查看控制台输出目录：generated/apple_tree_001、apple_tree_002……；橙子独立按 orange_tree_001 递增。
不会覆盖旧目录，也不回填失败的编号。不要删除 generated/.asset-numbering.json。
此步骤生成可编辑的 asset.blend，不生成素材级 asset_metadata.json。

### 2. 人工检查并保存

直接在 Blender 中打开对应目录的 asset.blend，检查树形、材质、果实方向和连接、不合理穿模，调整后保存。
不要只修改 scene.blend，也不要只保留未保存的界面编辑。
保留 Tree、OrchardTree_Asset、asset_role、已有 fruit_id；复制果实须给副本分配唯一 ID，已有 ID 不重排。
根节点保持米制、单位缩放；可以平移、旋转整株树，也可以调整外观网格。

### 3. 生成素材级 metadata

在 configs/export_metadata.json 中填写已审核素材目录，例如：

```json
"assetDir": "generated/apple_tree_008"
```

这只是填写示例，以实际生成目录为准。assetDir 默认留空，不自动选择最新文件。
可填写 reviewer、reviewNote；人工审核完成时使用 reviewMode=declared，自动测试使用 automated_test。
正常导出保持 verifyOnly=false、dryRun=false；保存配置后直接运行 generate_metadata.py。

结果写入该素材目录：asset_metadata.json、validation_report.json、metadata.log。
脚本只读取已保存模型，不重新建树、不改模型、不重新编号；再次提取前将旧描述备份到该素材目录的 history/。
之后若人工修改或重存了模型，必须重新提取描述；加载时应核对 model_sha256。

verifyOnly=true 时只检查已有描述、不生成新描述；dryRun=true 时只显示计划。
checkAttachments=true 可额外检查果柄连接，但不能证明整棵树完全无穿模。
所有相对路径都以项目根目录为基准，建议使用 `/`；JSON 不支持注释，字段拼错或类型错误会报错。

## 文件分工

| 内容 | 作用 |
|---|---|
| 根目录三个 Python 文件 | 唯一日常制作入口 |
| configs/ | 苹果、橙子、metadata 三份工作配置 |
| scripts/ | 内部启动、建树、材质/果柄处理、素材导出和校验；不需要逐个运行 |
| assets/、bark_texture/、leaf_texture/ | 叶果基础模型、连接标定与贴图，不能删除 |
| vendor/ | 两种建树算法与参数来源；部分文件以 AST 读取，不能因名字旧而删除 |
| .runtime/ | 配套 Blender、PowerShell 和隔离运行设置 |
| .run/ | 三个 PyCharm 运行配置 |
| generated/ | 素材输出及连续编号状态 |
| docs/ | 素材字段说明、来源/授权说明和精简项目清单 |
| tests/ | 当前流程回归测试及最近检查结果，不是制作入口 |
| hdri/ | 可选渲染预览使用的背景资源 |

最终单株交付仍为 asset.blend + asset_metadata.json。
metadata.json 是构建记录，不是素材级描述；scene.blend 是构建时的调试场景，不会自动同步人工修改。
frames=0 时不额外渲染图像；frames>0 的 images/ 仅为预览，不是完整训练数据集。

## 当前范围与注意事项

- 元数据保留实际外观包围盒、部件数量和逐果位置，不输出逐叶记录；精细形状由模型保存，包围盒不是精细碰撞体。
- 不生成碰撞代理，也不构建果园、导航或智能体训练流程。
- maturityStage / fruitVariantId 只是果实标签，不自动生成对应成熟度外观；当前不考虑整树生育阶段。
- 物种、品种、尺寸和成熟度没有完成实测标定；人工审核记录不是自动无穿模证明。
- 旧素材的读取/重新提取所需兼容校验仍是内部依赖，保留；旧碰撞数据不会被当成本版已验证功能。
- 资产与字段含义见 docs/asset_metadata.md；第三方素材来源及授权状态见 docs/THIRD_PARTY_NOTICES.md。


## 检查

```text
python -B -m unittest discover -s tests -v
```

测试用于检查配置、编号、模型/描述一致性等，不替代人工外观审核。最新结果保存为 tests/validation_latest.json。
