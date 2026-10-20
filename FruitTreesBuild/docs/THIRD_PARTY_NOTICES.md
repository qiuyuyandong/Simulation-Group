# 来源与授权状态

本文件保留原项目来源说明，替代带有旧版安装步骤、失效示例路径的上游 README 副本。
下列链接来自项目已有的来源记录，未在本次代码清理中重新审查网页或核定模型/贴图授权。

## 框架与算法

- IAMPS2019 框架：https://github.com/tduboudi/IAMPS2019-Procedural-Fruit-Tree-Rendering-Framework 。原 README 列出的代码作者为 Thomas Duboudin、Maxime Petit、Sridhar Ragupathi、Liming Chen；根目录 LICENSE 保留框架代码许可文本。
- Space Tree：https://github.com/varkenvarken/spacetree 。原作者与许可声明保留在 vendor/spacetree/src/add_mesh_space_tree/__init__.py，算法核心为 scanew.py。现代入口仅加载算法和读取 ellipsoid2，不注册旧插件界面。
- Sapling：https://github.com/blender/blender-addons/tree/main/add_curve_sapling 。归档实现及其源码许可保留在 vendor/sapling/utils.py；原 IAMPS 参数来源保留在 vendor/iamps/sapling_tree_scene_gen.py。

这些原始文件仍被当前程序读取，属于运行依赖，不是可以直接删除的旧入口。
vendor 源码头部和原作者声明不因项目清理而移除。详细固定来源记录见 project_manifest.json。

## 模型、贴图与背景

- 苹果基础模型：https://free3d.com/3d-model/apples-42451.html
- 橙子基础模型：https://www.turbosquid.com/3d-models/free-3ds-model-orange-resolution-photorealistic/756550
- Space Tree 叶片来源：http://pngimg.com/download/3638 、http://pngimg.com/download/3668
- Sapling 叶片来源：https://www.textures.com/download/leaves0089/21795?q=leaves
- 树皮来源：https://www.textures.com/download/3dscans0062/127610?q=cedar+tree
- 原 HDRI 来源：https://hdrihaven.com/hdri/?c=outdoor&h=spruit_sunrise

模型/UV/材质原型保存在 assets/source_prototypes.blend，来源与校验值记录保留在 assets/source_prototypes.json。
原型说明中的 source_scene 是历史来源，不是当前运行必需的文件路径。
第三方模型和贴图的授权状态继续标为 not_reviewed，不能用框架代码许可代替它们的许可，也没有将它们声明为“无版权”或 CC0。
