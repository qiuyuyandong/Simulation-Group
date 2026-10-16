spacetree
=========

## Blender 5.2.1 可分享适配版

修复版为 0.2.17，更新了注册、属性声明、集合、选择、光标、射线检测、矩阵及菜单接口。附带材质库已转换为 Blender 5.2 格式，保留原有 18 种材质和 36 个对象；4 张贴图已内嵌，材质和粒子选项使用稳定的原始库标识，重复运行不会因自动改名而失效。

安装时先禁用旧版，通过 Preferences → Add-ons → Install from Disk 安装下列 ZIP，保存工作并重启 Blender，再启用 SCA Tree Generator，确认版本为 0.2.17。

分享或重新安装时，使用 `release/SCA_Tree_Generator_0.2.17_Blender_5.2.1.zip`。生成入口为 Add → Mesh → Add Tree to Scene。详细说明见 `src/add_mesh_space_tree/使用说明.md`。插件按自身安装目录加载资源，不依赖本机盘符或用户名。场景脚本的水果模型、叶片贴图和 HDRI 需要另行分享。

旧 C 扩展不能用于当前 Blender Python，继续使用插件原有的纯 Python 回退实现；较大的树会耗时更长。已验证 Blender 5.2.1，5.0 不受此版本支持。原来的 Blender 2.x 材质压缩包和安装包保留供回退使用。新版另增加可选初始骨架接口，保留原操作器调用；Blender Skin在皮肤成形后再细分，距离提示改为实际单位。以下为原项目的历史说明。

A Blender add-on to create tree objects with the space colonization algorithm

Currently part of Blender contrib:

https://svn.blender.org/svnroot/bf-extensions/contrib/py/scripts/addons/add_mesh_space_tree/

Documentation (work in progress):

http://wiki.blender.org/index.php/Extensions:2.6/Py/Scripts/Add_Mesh/Add_Space_Tree

Current developments can be followed on BlenderArtists:

http://blenderartists.org/forum/showthread.php?282550-A-new-tree-add-on

Note
====

a commercial version of this add-on is available on Blender Market:
https://blendermarket.com/creators/varkenvarken

INSTALLATION
============

If you have installed Blender from a daily build, this add-on is already bundled. If you want to try a newer version you have to make sure that the distributed version is removed first:

- quit Blender
- go to the installation directory of the contributed addons, e.g. <BlenderInstallDir>\2.69\scripts\addons_contrib
- remove the add_mesh_space_tree directory
- download add_mesh_space_tree.zip from the release directory (do not use the download as .zip for the complete repository, that won't work: the .zip in the release dir is a package Blender cn use directly)
- open Blender
- choose File->User preferences->Addons->Install from file and select the downloaded .zip, click install
- don't forget to check the enable addon checkbox once it it is installed

Likewise, when installing an even newer version (i.e. after you have replaced the distributed version) you need to make sure nothing remains in the user data folder, so you'll then have to perform the steps aboce for the directory:

C:\Users\<username>\AppData\Roaming\Blender Foundation\Blender\2.69\scripts\addons

(on Windows taht is, I am not sure where this lives exactly on Unix systems)

If you want to enable the addon later, it lives in the Add Mesh section of the addons and is called 'SCA Tree generator'.

To use the addon (in the 3DVIEW) click Add->Mesh->Add tree to scene, the options are in the toolbar panel (Ctrl-T)

NOTE: the tree is generated at the position of the 3d cursor. If you don't see the tree, check that you can see the cursor.

NOTE: generating a tree can take quite some time, therefore the tree does NOT change immediately if you tweak an option. You have to click the 'update tree' button to generate a new tree after you changed the settings. 



