# 脚本整体封装清单（SCRIPT INVENTORY）
**版本**：V47 | **日期**：2026-09-19 | **脚本总数**：165
**封装原则**：维护链（run_maintenance_wrapper/run_poll_wrapper）引用的脚本一律标记【链内-勿动】；其余一次性修复/排查脚本标记【可归档】。本清单是脚本治理的权威索引。

## 一、调度入口（wrapper，最高优先级）
- run_maintenance_wrapper.py【链内-勿动】每日03:00维护链，串联27脚本，开头跑bridge巡检
- run_poll_wrapper.py【链内-勿动】群消息轮询（heartbeat+learning_system）
- run_morning_wrapper.py / run_noon_wrapper.py / run_evening_wrapper.py【链内-勿动】早/午/晚报

## 二、核心服务脚本（88个，日常运行依赖）
### LLM网关（8）
llm_router★ / coze_gateway★ / deepseek_gateway / llm_fallback / llm_guard / system_rag★ / rag_guard / coze_batch_tasks★（★=本轮实测PASS）
### 群指令（5）
v15_command_router / v15_features / task_insight_extension / task_ops_cli / task_selfheal
### 学习闭环（20）
learning_system【链内】/ wrong_book【链内】/ mastery_recalc★【链内】/ weekly_learning_report【链内】/ profile_evolve【链内】/ personalized_recommender【链内】/ knowledge_evolution【链内】/ knowledge_extension / knowledge_gap_analysis / feynman_workflow / feynman_verify / insight_to_card【链内】/ cold_archive_auto / daily_review / weekly_review / learning_retention_eval / cognitive_analysis_v13 / memory_hierarchy / pomodoro / time_block_plan【链内】
### 三察推送（9）
insight_daily / fetch_external_data / alert_fail / wecom_push + 4个wrapper（见一）
### 健康监控运维（14）
bridge_health_check★【链内】/ system_health_check★ / dashboard_health_check / heartbeat【链内】/ service_watchdog【链内】/ slo_monitor【链内】/ uptime_monitor【链内】/ health_monitor【链内】/ dlq_consumer【链内】/ idempotency / observability / system_logger / auto_restart【链内】/ boot_recover
### 备份灾备（6，全部【链内-勿动】）
backup_with_rotation / hourly_backup / offsite_replicate / recovery_drill / restore_drill / rollback
### Obsidian同步（3）
obsidian_sync / obsidian_reverse_archive / feishu_obsidian_reconcile
### 审计测试（17，部分【链内】）
data_audit / data_consistency_check【链内】/ security_audit【链内】/ cost_audit_v13 / invariant_assertions / golden_e2e / golden_write_e2e / redteam_suite【链内】/ chaos_drill【链内】/ regression_baseline / acceptance_run / eval_build / eval_run / offline_model_eval / independent_sample / independent_verify【链内】/ reproduce_all
### MCP桥接（2）
anyllm_bridge★ / feishu_mcp_cli
### 导入导出语音（4）
import_knowledge / v36_export_tables / todo_export_docx / voice_io
### 维护链专用工具（被wrapper引用，名字像临时但勿动）
cleanup_test_data【链内】/ efficiency_objective【链内】/ efficiency_baseline / quickstart / config_local / config_local.example / monthly_report_v13 / patch_health_fields / p0_features / p1_1_user_profile / p1_2_mastery_trend / p1_3_knowledge_gap / v19_integration / batch_create_tasks / update_backup_tables / update_heartbeat_tasks / log_stats_v13

## 三、可归档脚本（建议移 scripts/archive/，约50个，均未被wrapper引用）
### 一次性修复 fix_*（17）
fix_action_create_task / fix_batch_receipt / fix_create_receipt_filter / fix_create_task_all / fix_immediate_reply / fix_immediate_v2 / fix_insert_create_task / fix_looks_like / fix_new_task / fix_parse_new_task / fix_receipt_filter / fix_smart_cloud / fix_smart_connections_config / fix_smart_scope / fix_task_before_extension / fix_third_task / batch_fix_run_cmd
### 一次性排查 check_*（13）
check_1329 / check_all_test_tasks / check_dup_time / check_event_log / check_group_msgs / check_pm / check_profile_fields / check_real_user / check_smart_config / check_third_exact / check_third_test / check_todo_tasks / compare_sender
### 运维诊断 ops_*（12）
ops_config_startwhenavailable / ops_confirm_whitelist / ops_diagnose_1 / ops_diagnose_2 / ops_diagnose_heartbeat / ops_diagnose_writelog / ops_final_verify / ops_final_verify2 / ops_fix_heartbeat_dlq / ops_parse_fields / ops_test_source_severity / ops_test_whitelist / ops_v39_full_diagnose
### git/优化/杂项（约10）
dulwich_commit / dulwich_commit_simple / dulwich_commit_v2v5 / dulwich_remove_tests / optimize_archive / optimize_interval / optimize_morning / optimize_reports / optimize_tasks / find_third / get_source_options / mget_compare / verify_parse / test_siliconflow / read_baseline / cleanup_test_tables / create_test_task

## 四、归档操作安全规约
1. 归档前再次确认不在 run_maintenance_wrapper.py / run_poll_wrapper.py 引用清单（本清单第二节已核）。
2. 归档后必须回归：bridge_health_check + system_health_check 全PASS才算完成。
3. 归档只移动不删除；archive/ 不进计划任务、不进PATH。
4. 第三节清单可整批移动，第二节清单禁止移动。
