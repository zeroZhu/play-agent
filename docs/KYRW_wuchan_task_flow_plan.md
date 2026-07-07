# 课业任务（悟禅）真机取材与开发计划

## 本次环境

- 日期：2026-07-07
- 设备 serial：`127.0.0.1:16416`
- 分辨率：`1280x720`
- 素材目录：`screenshots/kyrw_wuchan_20260707/`

## 已确认流程

1. 打开活动面板并停留在「江湖」tab。
   - 素材：`01_activity_jianghu_wuchan_entry.png`
   - 「悟禅」入口在左上区域，第一层「前往」坐标约 `(215, 276)`。

2. 点击「悟禅」第一层「前往」后进入悟禅玩法子面板。
   - 素材：`02_after_wuchan_forward_5s.png`
   - 子面板包含「课业」「闲趣」「纳穗」「会武」。
   - 「课业」下方「前往」坐标约 `(276, 498)`。
   - 素材：`03_wuchan_detail_course_forward.png`

3. 点击「课业 / 前往」后退出活动面板并自动寻路到课业 NPC。
   - 自动寻路素材：`04_after_course_forward_4s.png` 至 `08_auto_path_24s.png`
   - NPC：普照 `<少林大师兄>`

4. 到达 NPC 后弹出对话，右侧有「悟禅」按钮。
   - 素材：`09_npc_puzhao_wuchan_button.png`
   - 「悟禅」按钮坐标约 `(1100, 465)`。

5. 点击「悟禅」后进入确认对话，右侧按钮变为「确定」。
   - 素材：`10_after_accept_2s.png`
   - 确认按钮坐标仍约 `(1100, 465)`。
   - 素材：`11_npc_confirm_dialog.png`

6. 点击「确定」后进入课业选择面板。
   - 素材：`13_course_selection_three_difficult.png`
   - 当前显示三张困难课业卡：
     - 罗汉堂课业
     - 禅医寮课业
     - 悟禅场课业

## 已解除的阻断状态

三张课业卡单独点击后均未进入课业，而是弹出提示：

> 请先完成当前布置的课业。

对应素材：

- `26_single_tap_wuchanchang_toast.png`
- `32_single_tap_luohantang_toast.png`
- `33_single_tap_chanyiliao_toast.png`

这说明当前账号已经存在一门已布置但未完成的课业。用户手动接取/恢复该课业后，左侧任务栏出现可追踪条目，后续已完成完整流程取材。

额外风险点：

- 点击「刷新」会弹出消耗「飞雪剑」确认框，当前数量显示 `0/10`。
- 脚本必须默认取消该弹窗，不能误点「确定」。
- 素材：`19_refresh_confirm_flying_snow_sword.png`

## 已完成课业流程

1. 用户手动恢复当前布置课业后，主界面左侧出现追踪：
   - `[课业] 门内历练(1/5)`
   - `与少林弟子对话`
   - `对话练武弟子(0/1)`
   - 素材：`36_manual_accept_current_state.png`
   - 点击追踪坐标约 `(125, 217)`。

2. 点击追踪后进入自动寻路。
   - 素材：`37_after_tap_course_tracker.png`
   - 自动寻路/对话过程素材：`38_course_path_or_dialog.png` 至 `40_course_path_or_dialog.png`

3. 到达后进入普照剧情对话。
   - 文案：`阿弥陀佛，近日达摩院的瓦片总会莫名滑落，砸到些花花草草。师门命你前去调查一番。`
   - 素材：`40_course_path_or_dialog.png`
   - 右下继续箭头坐标约 `(1230, 690)`。

4. 点击继续后，任务推进到：
   - `[课业] 教训恶徒(4/5)`
   - `奔赴禅医寮`
   - `搜索(0/1)`
   - 素材：`41_after_first_dialog_next.png`
   - 注：本次账号从 `1/5` 对话后直接进入 `4/5`，未出现独立的 `2/5`、`3/5` 可操作截图。

5. `4/5` 自动寻路结束后进入最后一环：
   - `[课业] 采买货品(5/5)`
   - `采买师门所需`
   - 需提交 `干粮·胡麻饼 0/18`
   - 弹出「获取途径」面板，唯一可见路径为「商城购买」。
   - 素材：`45_stage_4_path_or_search.png`
   - 获取途径面板素材：`46_stage_5_acquire_route_mall.png`
   - 「商城购买」入口坐标约 `(432, 246)`。

6. 点击「商城购买」进入珍宝阁。
   - 素材：`47_after_tap_mall_route.png`
   - 目标物品：`干粮·胡麻饼`
   - 单价：`48`
   - 默认数量：`1`
   - 左侧任务要求：`0/18`
   - 加号坐标约 `(1098, 584)`，需要点击 17 次将数量加到 `18`。
   - 数量 18 素材：`48_mall_quantity_18.png`

7. 点击购买按钮。
   - 购买按钮显示总价 `864`，坐标约 `(949, 663)`。
   - 购买后右侧出现「提交道具」面板，显示已拥有 `18` 个。
   - 素材：`49_after_buy_18_humabing.png`

8. 点击「一键提交」。
   - 坐标约 `(1078, 421)`。
   - 提交后弹出完成对话。
   - 素材：`50_after_one_key_submit_goods.png`

9. 完成弹窗：
   - 文案：`今日的课业已经全部完成，师弟辛苦了。`
   - 确定按钮坐标约 `(854, 508)`。
   - 素材：`51_course_complete_dialog.png`

10. 点击确定并退出商城后，左侧课业追踪消失，主界面只剩其他江湖任务。
    - 素材：`52_after_complete_ok.png`
    - 最终状态：`53_after_exit_mall_final_state.png`

## 脚本开发计划

### 任务文件

- 新增：`src/ymjh_bot/task/KYRW_task.py`
- 类名建议：`KyrwTask`
- `task_key = "KYRW"`
- `task_name = "课业任务"`
- 继承：`YmGameTask`

### 需要裁剪的模板

从本次素材优先裁剪：

- 活动页悟禅入口/第一层「前往」
  - 来源：`01_activity_jianghu_wuchan_entry.png`
- 悟禅子面板「课业」入口/「前往」
  - 来源：`03_wuchan_detail_course_forward.png`
- NPC 对话「悟禅」按钮
  - 来源：`09_npc_puzhao_wuchan_button.png`
- 课业选择面板标题/三张课业卡状态
  - 来源：`13_course_selection_three_difficult.png`
- “请先完成当前布置的课业”提示
  - 来源：`26_single_tap_wuchanchang_toast.png`
- 刷新消耗飞雪剑确认弹窗
  - 来源：`19_refresh_confirm_flying_snow_sword.png`

可复用现有模板：

- `btn_HD.png`
- `btn_close.png`
- `btn_pane_close.png`
- `btn_OK.png`
- `btn_modal_cancel.png`
- `text_zidongxunlu.png`
- `icon_task_active.png`
- `icon_task_rw.png`
- `icon_task_jh.png`

### 状态机设计

1. `close_all`
   - 关闭弹窗。
   - 处理省电模式和聊天框。

2. `resume_existing_course`
   - 优先检查是否已有「当前布置课业」。
   - 打开左侧任务栏，在「任务」「江湖」页签滚动查找课业关键字/模板。
   - 若找到，点击追踪并跳转到 `run_course_flow`。
   - 若未找到，继续活动接取流程。

3. `open_wuchan_activity`
   - 打开活动面板。
   - 切换「江湖」tab。
   - 定位并点击「悟禅」第一层「前往」。

4. `enter_course_from_wuchan_panel`
   - 在悟禅子面板点击「课业 / 前往」。
   - 等待回到主界面并出现自动寻路。

5. `wait_to_course_npc`
   - 等待 `text_zidongxunlu.png` 消失。
   - 等待 NPC 对话「悟禅」按钮出现。

6. `accept_or_open_course_panel`
   - 点击 NPC 对话「悟禅」。
   - 点击「确定」。
   - 进入课业选择面板。

7. `handle_course_panel`
   - 若点击课业卡出现“请先完成当前布置的课业”，关闭面板并回到 `resume_existing_course`。
   - 若出现刷新消耗确认，点击取消。
   - 若后续观察到可接取态，按配置选择课业卡。
   - 默认不刷新课业，避免消耗飞雪剑。

8. `run_course_flow`
   - 循环处理课业执行过程：
     - 点击左侧课业追踪。
     - 等待自动寻路。
     - 处理 NPC 对话确认。
     - 处理可能的战斗，复用 `auto_battle`。
     - 处理提交/领取/继续箭头。
     - 处理第 5 环「获取途径 -> 商城购买 -> 设置数量 -> 购买 -> 一键提交」。
   - 课业子流程存在随机性，建议用通用循环而不是写死 `1/5` 到 `5/5` 的每一步。

9. `verify_completion`
   - 重新打开悟禅课业入口。
   - 若不再出现“当前布置课业未完成”提示，或活动入口消失/出现完成态，则判定完成。

### 仍建议补充的真机素材

- 另一次新课业从 `1/5` 到 `5/5` 的完整随机分支，尤其是本次未独立出现的 `2/5`、`3/5`。
- 非商城购买型获取途径，例如摆摊、仓库、采集或战斗提交。
- 已完成后重新打开「悟禅 / 课业」入口的活动页完成态。

### 测试计划

- 新增 `tests/test_kyrw_task.py`
  - 校验任务类可加载。
  - 校验步骤顺序。
  - 校验关键 ROI 和坐标缩放。
  - 用本次截图做模板匹配单测。
- 真机回归：
  - 指定 serial：`127.0.0.1:16416`
  - 先跑只读/取材模式，确认不会误点刷新确认。
  - 再跑完整流程。
