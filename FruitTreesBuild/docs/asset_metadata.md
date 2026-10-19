# 素材级元数据 schema 3.0.0

主交付：`asset.blend` + `asset_metadata.json`。操作方式见项目根目录 README.md。
先生成、人工调整并保存模型，再运行独立的 `generate_metadata.py`。
运行前修改 `configs/export_metadata.json` 的 assetDir，正常运行参数留空；默认不自动选择最新素材。
提取与重新加载检查均只读模型，不修改模型几何、ID、版本或自定义属性。

| 字段 | 含义与来源 |
|---|---|
| schema_version | JSON 格式版本；3.0.0 表示不含碰撞扩展的外观素材描述 |
| asset_id | 模型中的稳定素材身份，与目录编号不同 |
| asset_version | 作者维护的版本标签；脚本只读取，不自动递增 |
| model_file / model_sha256 | 相对文件名及本次实际读取文件的 SHA-256 |
| asset_root | 根对象 Tree、集合 OrchardTree_Asset、集合类型和独立场景引用 |
| category / biological_info | 作物标签、品种信息与未标定状态；不含整树生育阶段 |
| coordinate_system | 米、右手、+Z 向上；原点约定为树根基部，矩阵按行存储并乘列向量 |
| bounds_local | 在 Tree 局部坐标系中，由外观求值几何计算的 AABB；包含木质、叶、果及独立果柄 |
| parts_summary | 实际叶片、果实与外观对象数量、允许的角色；不输出逐叶记录 |
| fruits | 每个果实的稳定 ID、对象引用、实际局部中心/范围、素材变体和成熟度标签 |
| generation | 方法、种子、构建时 Blender 版本与追溯指纹；不是人工调整后的目标真值 |
| provenance | 框架、算法、第三方模型贴图来源，以及授权未审核状态 |
| review | 本次用户审核声明或 automated_test_only、审核人、备注、记录时间和对应模型 SHA-256 |
| quality | 实际检查范围与限制；历史非外观对象忽略数量，不宣称无穿模或提供物理碰撞 |

## 果实字段

| 字段 | 含义 |
|---|---|
| fruit_id | 稳定唯一 ID；人工删除后不补号，新建或复制的果实必须另给唯一 ID |
| object_ref | 当前模型里的对象名称 |
| center_local_m | 当前外观几何局部 AABB 的中点，单位米；不是重心、抓取点或果柄端点 |
| bounds_local | 当前果实求值几何的局部 AABB；不使用生成参数中的目标直径代替 |
| fruit_variant_id | 使用的果实素材变体；旧模型未标注时为 `<crop>_unspecified` |
| maturity_stage | unknown / unripe / turning / ripe；显式标签，不从颜色自动判断 |

精细外形保存在 asset.blend 的网格中；包围盒只表示最大范围，不是枝叶精细轮廓，也不是后续可直接使用的精细碰撞体。
逐果 attachment 特征不作为核心字段，避免人工移动后继续输出旧连接坐标。可选附加连接诊断写入 validation_report.json。

## 与旧格式的区别

- 保留稳定身份、单位、外观包围盒、逐果记录、来源和成熟度预留。
- 移除 collision 模块、asset_root.collision_container 和 fruits[].collision_enabled。
- 移除碰撞拟合、覆盖范围、代理网格及碰撞校验标志；不再要求模型保留旧碰撞流程所依赖的中心线结构。
- review 不再依赖写入模型的旧定稿记录，而由本次描述提取明确记录。
- 不新增逐叶元数据、精细轮廓点集、相机、整树生育阶段或环境布局字段。
- schema 1.0/1.1 可读并保留原外观校验；schema 2 可读核心外观字段，但历史物理扩展不再验证。不能将本版的外观检查通过解读为其旧碰撞模块检查通过。

历史文件不会批量改写。为旧文件重新提取时，只读取当前外观，忽略已知历史代理角色并报告数量；不会删除模型中的旧对象。

## 后续环境使用

环境 metadata 保存素材引用和实例的 transform_asset_to_world；果实世界位置可通过 fruit_world_records() 派生，不重复作为资产真值维护。
实例加载时将 Tree 的世界变换设为环境实例矩阵，不与文件中原有根节点世界姿态重复叠乘。
本版只提供外观素材与描述，不提供导航、智能体、动态物理或静态碰撞注册；未提供不能视为检查通过。

审核声明不能证明人工动作已经发生，自动测试样例明确标为 automated_test_only。范围、模型物种、成熟度和无穿模均不冒充已经实测验证。
